from typing import Literal
from dataclasses import replace
import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import secrets
from fastapi import FastAPI, Request, HTTPException, Query, BackgroundTasks
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func, case
from app.api.schemas import (
    SelectedPlanRequest,
    ScanRequest,
    ReviewRequest,
    PlanRequest,
    ExecuteRequest,
    RestoreRequest,
)
from app.core.config import Settings, data_directory, authentication_token
from app.core.filesystem import identity, stored_identity
from app.core.logging import configure
from app.database.session import open_database
from app.database.models import (
    FileReviewChoice,
    ScanJob,
    Volume,
    File,
    MediaMetadata,
    DuplicateGroup,
    GroupMember,
    Setting,
    CleanupOperation,
)
from app.workers.manager import JobManager
from app.cleanup.service import CleanupService, group_error
from app.metadata.extract import tools
from app.metadata.decoding import load_still


def record(model):
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}


def create_app(directory: Path | None = None, token: str | None = None, frontend: Path | None = None):
    directory = directory or data_directory()
    directory.mkdir(parents=True, exist_ok=True)
    api_token = token or authentication_token(directory)
    engine, sessions = open_database(directory / "media-cleaner.sqlite3")
    configure(directory)
    from app.retention.recommend import initialize_exact_selections

    initialize_exact_selections(sessions)

    def settings():
        with sessions() as session:
            saved = session.get(Setting, "application")
            return Settings.model_validate(saved.value) if saved else Settings()

    manager = JobManager(sessions)
    cleanup = CleanupService(sessions, settings)
    cleanup.recover_interrupted()

    @asynccontextmanager
    async def lifespan(_app):
        yield
        manager.prepare_shutdown()
        engine.dispose()

    app = FastAPI(
        title="Media Cleaner",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.sessions, app.state.manager, app.state.cleanup = sessions, manager, cleanup
    app.state.shutdown_callback = None

    @app.middleware("http")
    async def local_access(request: Request, call_next):
        host = request.headers.get("host", "")
        hostname = host.split(":")[0]
        if hostname not in {"127.0.0.1", "localhost"}:
            return JSONResponse(
                {"error": {"code": "host_rejected", "message": "Loopback access only"}}, status_code=403
            )
        if request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            allowed = {f"http://{host}", "http://127.0.0.1:5173", "http://localhost:5173"}
            bearer = request.headers.get("authorization", "").removeprefix("Bearer ")
            explicit = secrets.compare_digest(bearer, api_token)
            cookie = request.cookies.get("media_cleaner_session", "")
            if request.url.path != "/api/v1/session" and not (
                explicit or secrets.compare_digest(cookie, api_token)
            ):
                return JSONResponse(
                    {"error": {"code": "unauthorized", "message": "Connect using the local launch token"}},
                    status_code=401,
                )
            if (origin and origin not in allowed) or (
                request.method not in {"GET", "HEAD"} and not origin and not explicit
            ):
                return JSONResponse(
                    {"error": {"code": "origin_rejected", "message": "Local origin required"}},
                    status_code=403,
                )
            if (
                manager.stopping
                and request.method not in {"GET", "HEAD"}
                and request.url.path != "/api/v1/app/shutdown"
            ):
                return JSONResponse({"error": {"message": "App shutdown is in progress"}}, status_code=503)
            if request.method in {"POST", "PUT"}:
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 1_048_576:
                        return JSONResponse(
                            {"error": {"code": "request_too_large", "message": "Request exceeds 1 MiB"}},
                            status_code=413,
                        )
                request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"
        )
        return response

    @app.exception_handler(ValueError)
    async def bad_value(_request, exc):
        return JSONResponse({"error": {"code": "invalid_operation", "message": str(exc)}}, status_code=400)

    @app.exception_handler(OSError)
    async def filesystem_error(_request, exc):
        return JSONResponse(
            {
                "error": {
                    "code": "filesystem_error",
                    "message": f"{type(exc).__name__}: filesystem unavailable or permission denied",
                }
            },
            status_code=409,
        )

    @app.exception_handler(HTTPException)
    async def http_error(_request, exc):
        return JSONResponse(
            {"error": {"code": str(exc.status_code), "message": str(exc.detail)}}, status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, exc):
        return JSONResponse(
            {
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request fields",
                    "details": [
                        {"loc": list(error["loc"]), "message": error["msg"], "type": error["type"]}
                        for error in exc.errors()
                    ],
                }
            },
            status_code=422,
        )

    @app.post("/api/v1/session")
    def connect(request: Request):
        if not secrets.compare_digest(request.headers.get("authorization", ""), f"Bearer {api_token}"):
            raise HTTPException(401, "Invalid launch token")
        response = JSONResponse({"connected": True})
        response.set_cookie("media_cleaner_session", api_token, httponly=True, samesite="strict")
        return response

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "phase": 3, "tools": tools(), "cleanup": ["trash", "quarantine"]}

    @app.get("/api/v1/openapi.json")
    def schema():
        return app.openapi()

    @app.get("/api/v1/settings")
    def get_settings():
        return settings()

    @app.put("/api/v1/settings")
    def put_settings(value: Settings):
        if value.cleanup_destination not in {"trash", "quarantine"} or value.theme not in {
            "system",
            "light",
            "dark",
        }:
            raise ValueError("Invalid cleanup destination or theme")
        value.protected_directories = [
            str(Path(path).expanduser().resolve()) for path in value.protected_directories
        ]
        value.excluded_directories = [
            str(Path(path).expanduser().resolve()) for path in value.excluded_directories
        ]
        value.excluded_extensions = [
            extension.lower() if extension.startswith(".") else "." + extension.lower()
            for extension in value.excluded_extensions
        ]
        with sessions.begin() as session:
            saved = session.get(Setting, "application")
            if saved:
                saved.value = value.model_dump()
            else:
                session.add(Setting(key="application", value=value.model_dump()))
        return value

    @app.post("/api/v1/folders/choose")
    def choose_folder():
        from app.core.folder_dialog import choose_directory

        return {"path": choose_directory()}

    @app.post("/api/v1/scans", status_code=201)
    def start_scan(request: ScanRequest):
        options = settings().model_dump() | request.model_dump()
        options["excluded_directories"] = list(
            set(options["excluded_directories"] + settings().excluded_directories + [str(directory)])
        )
        options["excluded_extensions"] = list(
            set(
                extension.lower() if extension.startswith(".") else "." + extension.lower()
                for extension in options["excluded_extensions"] + settings().excluded_extensions
            )
        )
        roots = []
        for text in request.roots:
            root = Path(text).expanduser().resolve(strict=True)
            if not root.is_dir():
                raise ValueError("Scan roots must be accessible directories")
            if root not in roots:
                roots.append(root)
        options["roots"] = [str(root) for root in roots]
        with manager.lock:
            if manager.stopping:
                raise ValueError("App shutdown is in progress")
            if manager.active and not manager.active.done():
                raise ValueError("Another scan is active")
            with sessions.begin() as session:
                job = ScanJob(options=options)
                session.add(job)
                session.flush()
                result = record(job)
            manager.start(job.id)
        return result

    @app.get("/api/v1/scans")
    def scans(offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=200)):
        with sessions() as session:
            return {
                "items": [
                    record(job)
                    for job in session.scalars(
                        select(ScanJob).order_by(ScanJob.created_at.desc()).offset(offset).limit(limit)
                    )
                ],
                "total": session.scalar(select(func.count()).select_from(ScanJob)),
            }

    @app.get("/api/v1/scans/active")
    def active_scan():
        with sessions() as session:
            job = session.scalar(
                select(ScanJob)
                .where(ScanJob.status.in_(["queued", "running", "paused", "interrupted"]))
                .order_by(
                    case((ScanJob.status.in_(["queued", "running"]), 0), else_=1), ScanJob.created_at.desc()
                )
                .limit(1)
            )
            return {"scan": record(job) if job else None}

    def get_scan(scan_id):
        with sessions() as session:
            job = session.get(ScanJob, scan_id)
            if not job:
                raise HTTPException(404, "Scan not found")
            from app.scanner.folder_cache import CACHE_NAME

            return record(job) | {
                "activity": manager.activity(scan_id), "checkpoint_at": job.updated_at,
                "checkpoint_storage": {
                    "database": str((directory / "media-cleaner.sqlite3").resolve()),
                    "folder_caches": [str(Path(root) / CACHE_NAME) for root in job.options["roots"]],
                },
            }

    @app.get("/api/v1/scans/{scan_id}")
    def scan(scan_id: str):
        return get_scan(scan_id)

    @app.post("/api/v1/scans/{scan_id}/{action}")
    def control_scan(scan_id: str, action: str):
        if action in {"checkpoint", "stop"}:
            manager.pause_at_checkpoint(scan_id, stop=action == "stop")
            return get_scan(scan_id)
        with manager.lock:
            if manager.stopping:
                raise ValueError("App shutdown is in progress")
            with sessions.begin() as session:
                job = session.get(ScanJob, scan_id)
                if not job:
                    raise HTTPException(404, "Scan not found")
                if action in {"pause", "cancel"} and job.status in {
                    "queued",
                    "running",
                    "paused",
                    "interrupted",
                }:
                    job.status = "paused" if action == "pause" else "cancelled"
                elif action == "resume" and job.status in {"paused", "interrupted", "failed"}:
                    if manager.active and not manager.active.done():
                        raise ValueError("Worker is stopping; try resume again shortly")
                    job.status = "queued"
                    session.commit()
                    manager.start(scan_id)
                else:
                    raise ValueError("This scan does not support that action in its current state")
                return record(job)

    def group_options(query, classification, sort):
        if classification:
            query = query.where(DuplicateGroup.classification == classification)
        order = {
            "discovered": [],
            "exact_first": [case((DuplicateGroup.classification == "EXACT_DUPLICATE", 0), else_=1)],
            "largest": [DuplicateGroup.recoverable.desc()],
            "most_files": [DuplicateGroup.member_count.desc()],
        }[sort]
        return query.order_by(*order, DuplicateGroup.first_seen_at, DuplicateGroup.id)

    @app.get("/api/v1/scans/{scan_id}/matches")
    def live_matches(
        scan_id: str, offset: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=50),
        classification: Literal["EXACT_DUPLICATE", "SIMILAR_CONTENT"] | None = None,
        sort: Literal["discovered", "exact_first", "largest", "most_files"] = "discovered",
    ):
        job = get_scan(scan_id)
        with sessions() as session:
            # SQLite legacy transaction mode does not begin on SELECT. Keep the
            # page and its counts in one snapshot while live groups are added.
            session.connection().exec_driver_sql("BEGIN")
            query = select(DuplicateGroup).where(
                DuplicateGroup.scan_id == scan_id,
                DuplicateGroup.member_count > 1,
                DuplicateGroup.review_status.not_in(["pending", "resolved"]),
            )
            rows = [
                record(group)
                for group in session.scalars(
                    group_options(query, classification, sort)
                    .offset(offset)
                    .limit(limit)
                )
            ]
            counts = dict(
                session.execute(
                    select(DuplicateGroup.classification, func.count())
                    .where(
                        DuplicateGroup.scan_id == scan_id,
                        DuplicateGroup.member_count > 1,
                        DuplicateGroup.review_status.not_in(["pending", "resolved"]),
                    )
                    .group_by(DuplicateGroup.classification)
                ).all()
            )
            return {
                "items": rows,
                "total": counts.get(classification, 0) if classification else sum(counts.values()),
                "exact_groups": counts.get("EXACT_DUPLICATE", 0),
                "similar_groups": counts.get("SIMILAR_CONTENT", 0),
                "provisional": job["status"] != "completed",
                "checkpoint_at": job["checkpoint_at"],
            }

    @app.get("/api/v1/scans/{scan_id}/selection-summary")
    def selection_summary(
        scan_id: str,
        classification: Literal["EXACT_DUPLICATE", "SIMILAR_CONTENT"] | None = None,
    ):
        get_scan(scan_id)
        with sessions() as session:
            selected = GroupMember.keep.is_(False) & (
                (DuplicateGroup.classification == "EXACT_DUPLICATE") |
                (DuplicateGroup.review_status == "reviewed")
            )
            query = select(
                func.count(func.distinct(File.id)),
                func.count(func.distinct(case((selected, File.id), else_=None))),
            ).select_from(File).join(GroupMember, GroupMember.file_id == File.id).join(
                DuplicateGroup, DuplicateGroup.id == GroupMember.group_id
            ).where(
                DuplicateGroup.scan_id == scan_id,
                DuplicateGroup.review_status.not_in(["pending", "resolved"]),
                DuplicateGroup.member_count > 1,
                File.status == "ready",
            )
            if classification:
                query = query.where(DuplicateGroup.classification == classification)
            total, selected_count = session.execute(query).one()
            return {"total_files": total, "selected_files": selected_count}

    @app.get("/api/v1/scans/{scan_id}/warnings")
    def scan_warnings(scan_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        get_scan(scan_id)
        with sessions() as session:
            query = (
                select(File, MediaMetadata)
                .outerjoin(MediaMetadata, MediaMetadata.file_id == File.id)
                .where(File.scan_id == scan_id, (File.error.is_not(None)) | (MediaMetadata.warnings != []))
            )
            items = [
                {
                    "id": file.id,
                    "name": file.name,
                    "path": file.path,
                    "warnings": ([file.error] if file.error else [])
                    + (metadata.warnings if metadata else []),
                }
                for file, metadata in session.execute(query.order_by(File.path).offset(offset).limit(limit))
            ]
            return {
                "items": items,
                "total": session.scalar(select(func.count()).select_from(query.subquery())),
            }

    @app.get("/api/v1/scans/{scan_id}/events")
    async def events(scan_id: str, request: Request):
        get_scan(scan_id)

        async def stream():
            previous = None
            while not await request.is_disconnected():
                state = get_scan(scan_id)
                payload = json.dumps(state)
                if payload != previous:
                    yield f"data: {payload}\n\n"
                    previous = payload
                else:
                    yield ": heartbeat\n\n"
                if state["status"] not in {"queued", "running"}:
                    break
                await asyncio.sleep(0.5)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
        )

    @app.get("/api/v1/volumes")
    def volumes():
        with sessions() as session:
            return {
                "items": [record(volume) for volume in session.scalars(select(Volume))],
                "note": "Observed volumes only. Unavailable roots are retained in scan history; device identity is session-local.",
            }

    @app.get("/api/v1/files")
    def files(
        scan_id: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        status: str | None = None,
    ):
        with sessions() as session:
            query = select(File).where(File.scan_id == scan_id)
            if status:
                query = query.where(File.status == status)
            return {
                "items": [
                    record(file)
                    for file in session.scalars(query.order_by(File.path).offset(offset).limit(limit))
                ],
                "total": session.scalar(select(func.count()).select_from(query.subquery())),
            }

    @app.get("/api/v1/files/{file_id}")
    def file_details(file_id: str):
        with sessions() as session:
            file = session.get(File, file_id)
            if not file:
                raise HTTPException(404, "File not found")
            metadata = session.get(MediaMetadata, file_id)
            return record(file) | {
                "metadata": metadata.fields if metadata else {},
                "warnings": metadata.warnings if metadata else [],
            }

    def preview_source(file):
        path, saved = Path(file.path), stored_identity(file)
        try:
            current = identity(path)
        except OSError:
            raise HTTPException(404, "Media unavailable; reconnect its drive")
        except ValueError:
            raise HTTPException(409, "Media path changed since scanning")
        # Device numbers can change after a drive is remounted. For viewing only,
        # accept that change when inode, size and both timestamps still match.
        # Keep the saved identity intact for cleanup and scan recovery checks.
        if replace(current, device=saved.device) != saved:
            raise HTTPException(409, "Media changed since scanning")
        return path, current

    @app.get("/api/v1/files/{file_id}/thumbnail")
    def file_thumbnail(file_id: str):
        from app.metadata.thumbnails import thumbnail

        with sessions() as session:
            file = session.get(File, file_id)
            if not file:
                raise HTTPException(404, "Media unavailable")
            processing = file.status == "discovered" and any(
                item.get("file_id") == file_id for item in manager.activity(file.scan_id)
            )
            if file.status != "ready" and not processing:
                raise HTTPException(404, "Media unavailable")
            path, expected = preview_source(file)
            try:
                data = thumbnail(str(path), expected.key(str(path)), file.media_type)
            except Exception:
                raise HTTPException(415, "Thumbnail unavailable for this format")
            if identity(path) != expected:
                raise HTTPException(409, "Media changed since scanning")
            return StreamingResponse(iter([data]), media_type="image/jpeg")

    @app.get("/api/v1/files/{file_id}/preview")
    def preview(file_id: str):
        with sessions() as session:
            file = session.get(File, file_id)
            if not file or file.status != "ready":
                raise HTTPException(404, "Media unavailable")
            path, expected = preview_source(file)
            if file.media_type == "image":
                from io import BytesIO

                try:
                    metadata = session.get(MediaMetadata, file_id)
                    if metadata and metadata.fields.get("animated"):
                        return FileResponse(path, media_type=file.mime_type)
                    image = load_still(path)
                    output = BytesIO()
                    image.save(output, "JPEG", quality=85)
                except Exception:
                    raise HTTPException(415, "Image preview unavailable; exact comparison still works")
                if identity(path) != expected:
                    raise HTTPException(409, "Media changed since scanning")
                return StreamingResponse(iter([output.getvalue()]), media_type="image/jpeg")
            return FileResponse(path, media_type=file.mime_type)  # Starlette supports byte ranges.

    @app.get("/api/v1/groups")
    def groups(
        scan_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
        classification: Literal["EXACT_DUPLICATE", "SIMILAR_CONTENT"] | None = None,
        sort: Literal["discovered", "exact_first", "largest", "most_files"] = "discovered",
    ):
        with sessions() as session:
            query = select(DuplicateGroup).where(
                DuplicateGroup.scan_id == scan_id,
                DuplicateGroup.review_status.not_in(["pending", "resolved"]),
            )
            return {
                "items": [
                    record(group)
                    for group in session.scalars(
                        group_options(query, classification, sort)
                        .offset(offset)
                        .limit(limit)
                    )
                ],
                "total": session.scalar(select(func.count()).select_from(group_options(query, classification, sort).subquery())),
            }

    @app.get("/api/v1/groups/{group_id}")
    def group(group_id: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
        with sessions() as session:
            group = session.get(DuplicateGroup, group_id)
            if not group:
                raise HTTPException(404, "Group not found")
            query = (
                select(File, GroupMember.keep)
                .join(GroupMember, GroupMember.file_id == File.id)
                .where(GroupMember.group_id == group_id, File.status == "ready")
            )
            members = []
            for file, keep in session.execute(query.order_by(File.path).offset(offset).limit(limit)):
                metadata = session.get(MediaMetadata, file.id)
                members.append(
                    record(file)
                    | {
                        "keep": keep,
                        "metadata": metadata.fields if metadata else {},
                        "warnings": metadata.warnings if metadata else [],
                    }
                )
            selected_count = session.scalar(select(func.count()).select_from(
                query.where(GroupMember.keep.is_(False)).subquery()
            ))
            return record(group) | {
                "files": members, "selected_count": selected_count,
                "ready_count": session.scalar(select(func.count()).select_from(query.subquery())),
            }

    @app.post("/api/v1/groups/{group_id}/review")
    def review(group_id: str, value: ReviewRequest):
        with manager.lock, sessions.begin() as session:
            group = session.get(DuplicateGroup, group_id)
            if not group:
                raise HTTPException(404, "Group not found")
            members = session.scalars(select(GroupMember).where(GroupMember.group_id == group_id)).all()
            ids = {member.file_id for member in members}
            if value.keep_all and (value.keep_ids is not None or value.changes):
                raise group_error(session, group_id, "Choose one review action at a time")
            keep_ids = ids if value.keep_all else (
                set(value.keep_ids)
                if value.keep_ids is not None
                else {member.file_id for member in members if member.keep}
            )
            if not set(value.changes) <= ids:
                raise group_error(session, group_id, "Changed files must belong to this group")
            for file_id, keep in value.changes.items():
                keep_ids.add(file_id) if keep else keep_ids.discard(file_id)
            if not keep_ids <= ids:
                raise group_error(session, group_id, "Keep IDs must belong to this group")
            explicit_keep_none = value.keep_ids == [] or (
                bool(group.evidence.get("allow_keep_none")) and not any(member.keep for member in members)
            )
            if (
                group.classification == "EXACT_DUPLICATE"
                and not explicit_keep_none
                and not any(session.get(File, file_id).status == "ready" for file_id in keep_ids)
            ):
                raise group_error(session, group_id, "Keep at least one file in each exact-duplicate group")
            for member in members:
                file = session.get(File, member.file_id)
                if file.protected_reason and member.file_id not in keep_ids:
                    raise group_error(session, group_id, "Protected assets must remain selected")
                member.keep = member.file_id in keep_ids
                choice = session.get(FileReviewChoice, (member.file_id, group.classification))
                if choice:
                    choice.keep = member.keep
                else:
                    session.add(
                        FileReviewChoice(
                            file_id=member.file_id, classification=group.classification, keep=member.keep
                        )
                    )
            group.evidence = dict(group.evidence, allow_keep_none=value.keep_ids == [] or (
                not keep_ids and bool(group.evidence.get("allow_keep_none"))
            ))
            group.review_status = "reviewed"
        for file_id in ids:
            manager.save_folder_cache(group.scan_id, file_id)
        return {"saved": True}

    @app.post("/api/v1/app/shutdown")
    def shutdown_app(value: RestoreRequest, background: BackgroundTasks):
        if not value.confirmed:
            raise ValueError("Confirm saving checkpoints and shutting down the app")
        callback = app.state.shutdown_callback
        if callback is None:
            raise HTTPException(
                503,
                "This server does not support app shutdown. Stop it from its terminal after saving a checkpoint.",
            )
        manager.prepare_shutdown()
        background.add_task(callback)
        return {"status": "stopped", "checkpoint_saved": True}

    @app.post("/api/v1/cleanup/plan-selected", status_code=201)
    def plan_selected(value: SelectedPlanRequest):
        with manager.lock:
            return record(cleanup.plan_selected(value.scan_id, value.destination, value.classification))

    @app.post("/api/v1/cleanup/plan", status_code=201)
    def plan(value: PlanRequest):
        with manager.lock:
            return record(cleanup.plan(value.file_ids, value.destination, value.group_id))

    @app.post("/api/v1/cleanup/execute")
    def execute(value: ExecuteRequest):
        with manager.lock:
            result = cleanup.execute(value.plan_id, value.token, value.confirmed)
            manager.matcher_dirty = True
            return record(result)

    @app.get("/api/v1/cleanup/{operation_id}/progress")
    def cleanup_progress(operation_id: str):
        # Reads must not wait for the execution lock held by cleanup.
        with sessions() as session:
            operation = session.get(CleanupOperation, operation_id)
            if not operation:
                raise HTTPException(404, "Cleanup plan not found")
            moved = [item for item in operation.items if item["status"] == "moved"]
            failed = [item for item in operation.items if item["status"] == "failed"]
            current = next((item for item in operation.items if item["status"] == "moving"), None)
            if current is None and operation.status == "executing":
                current = next((item for item in operation.items if item["status"] == "planned"), None)
            return {
                "id": operation.id,
                "status": operation.status,
                "total": len(operation.items),
                "processed": len(moved) + len(failed),
                "moved": len(moved),
                "failed": len(failed),
                "moved_bytes": sum(item["size"] for item in moved),
                "total_bytes": operation.total_bytes,
                "current_file": current["source"] if current else None,
                "current_action": "moving" if current and current["status"] == "moving" else "checking" if current else None,
            }

    @app.get("/api/v1/cleanup/history")
    def cleanup_history(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        with sessions() as session:
            return {
                "items": [
                    record(operation)
                    for operation in session.scalars(
                        select(CleanupOperation)
                        .order_by(CleanupOperation.created_at.desc())
                        .offset(offset)
                        .limit(limit)
                    )
                ],
                "total": session.scalar(select(func.count()).select_from(CleanupOperation)),
            }

    @app.post("/api/v1/cleanup/{operation_id}/restore")
    def restore(operation_id: str, value: RestoreRequest):
        if not value.confirmed:
            raise ValueError("Confirm recovery first")
        with manager.lock:
            return record(cleanup.restore(operation_id))

    @app.get("/api/v1/dashboard")
    def dashboard():
        with sessions() as session:
            latest = session.scalar(select(ScanJob).order_by(ScanJob.created_at.desc()).limit(1))
            if not latest:
                return {"files": 0, "bytes": 0, "groups": 0, "similar_groups": 0, "recoverable": 0}
            query = select(File).where(File.scan_id == latest.id, File.status.in_(["ready", "discovered"]))
            return {
                "scan_id": latest.id,
                "files": session.scalar(select(func.count()).select_from(query.subquery())),
                "bytes": session.scalar(
                    select(func.coalesce(func.sum(File.size), 0)).where(
                        File.scan_id == latest.id, File.status == "ready"
                    )
                ),
                "groups": session.scalar(
                    select(func.count())
                    .select_from(DuplicateGroup)
                    .where(
                        DuplicateGroup.scan_id == latest.id,
                        DuplicateGroup.review_status.not_in(["pending", "resolved"]),
                        DuplicateGroup.classification == "EXACT_DUPLICATE",
                    )
                ),
                "similar_groups": session.scalar(
                    select(func.count())
                    .select_from(DuplicateGroup)
                    .where(
                        DuplicateGroup.scan_id == latest.id,
                        DuplicateGroup.review_status.not_in(["pending", "resolved"]),
                        DuplicateGroup.classification == "SIMILAR_CONTENT",
                    )
                ),
                "recoverable": session.scalar(
                    select(func.coalesce(func.sum(DuplicateGroup.recoverable), 0)).where(
                        DuplicateGroup.scan_id == latest.id,
                        DuplicateGroup.review_status.not_in(["pending", "resolved"]),
                        DuplicateGroup.classification == "EXACT_DUPLICATE",
                    )
                ),
            }

    @app.get("/api/v1/diagnostics")
    def diagnostics():
        return FileResponse(
            directory / "diagnostics.jsonl",
            media_type="application/x-ndjson",
            filename="media-cleaner-diagnostics.jsonl",
        )

    frontend = frontend or Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app
