import { describe, it, expect, afterEach } from "vitest";
import {
  loadWorkspace,
  loadDraft,
  saveLocal,
  workspaceKey,
  draftKey,
} from "./workspace";
afterEach(() => localStorage.clear());
describe("saved scanner workspace", () => {
  it("restores the selected scan and scan options after refresh", () => {
    saveLocal(workspaceKey, { page: "Scanner", scanId: "running-id" });
    saveLocal(draftKey, {
      roots: "/photos",
      mode: "similar",
      sensitivity: "strict",
      hidden: true,
    });
    expect(loadWorkspace()).toEqual({ page: "Scanner", scanId: "running-id" });
    expect(loadDraft()).toMatchObject({
      roots: "/photos",
      mode: "similar",
      sensitivity: "strict",
      hidden: true,
    });
  });
  it("falls back safely for damaged or outdated browser storage", () => {
    localStorage.setItem(workspaceKey, "{");
    expect(loadWorkspace()).toEqual({ page: "Dashboard", scanId: "" });
    saveLocal(draftKey, { roots: 7, mode: "invalid", sensitivity: "invalid" });
    expect(loadDraft()).toMatchObject({
      roots: "",
      mode: "similar",
      sensitivity: "balanced",
    });
  });
});
