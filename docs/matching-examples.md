# Matching sensitivity photo examples

Generated with the built-in imagegen tool. Each selected level shows the original
hiker beside one changed version. Both apps display the same atlas cells.

| Level | Example difference | pHash / dHash | Subject cosine | Selected level matches |
| --- | --- | --- | --- | --- |
| Strict | Near-identical copy | 2 / 4 | 0.982 | Yes |
| Balanced | Small lighting edit | 2 / 3 | 0.967 | Yes |
| Loose | Small arm/head movement | 6 / 6 | 0.915 | Yes |
| Very loose | Reaching pose; sign removed | 8 / 8 | 0.876 | Yes |
| Extra loose | Different camera angle | 16 / 16 | 0.848 | Yes |
| Maximum | Changed pose and forest background | 22 / 18 | 0.873 | Yes |

Measured with the desktop matcher and bundled model. These examples illustrate
qualifying changes, not exclusive boundaries: a pair may qualify at multiple
levels. They do not guarantee that every similarly changed photo will match.

## Assets and layout

- Desktop: `apps/desktop/frontend/public/matching/sensitivity-scenes.png`
- Android: `apps/android/app/src/main/res/drawable-nodpi/matching_scenes.png`

The atlas has two columns and four rows, with no gutters. Cell 0 is the original;
cells 1–6 correspond to the sensitivity levels; cell 7 is unused. The earlier
canoe atlas remains available for existing matcher regression tests.

The desktop slider places six dots directly on its track, with clickable labels
aligned to those positions. Keyboard and drag interaction remain available.

## Initial generation prompt

Use case: scientific-educational. Asset: ONE photographic contact sheet used by a media similarity app. Create an exact TWO COLUMN by FOUR ROW grid, eight equal square photographic panels, no margins, no gutters, no borders, no text, no logos. Target 1024x2048 portrait. All panels show the SAME adult hiker, short dark hair, teal hiking jacket and bright yellow backpack, clearly visible in foreground. Keep identity, outfit, backpack and photographic realism consistent. Natural forest trail with a large tree, mossy rock and small wooden trail sign. Camera photo texture and detail, realistic daylight. Panel order reading left to right, top to bottom: 0 ORIGINAL hiker standing near mossy rock, facing slightly toward camera, hand resting on backpack strap; 1 STRICT almost identical copy of panel0, same position and geometry, only tiny exposure difference; 2 BALANCED same exact composition, modest brighter lighting and contrast; 3 LOOSE same scene and framing, hiker has slightly moved arm and head; 4 VERY LOOSE same scene and similar framing, hiker crouching beside rock, small wooden sign now absent; 5 EXTRA LOOSE same subject and forest scene photographed from a visibly different camera angle, subject in side profile, tree and rock shifted in perspective; 6 MAXIMUM same hiker and teal jacket/yellow backpack now seated in a different forest clearing, changed background and pose, old rock and sign absent; 7 repeat original panel0. Each panel fills its grid cell completely. This is a single contact sheet with EIGHT panels, exactly 2 columns and 4 rows. No captions.

## Final edit prompt

Edit this exact 2-column 4-row photographic contact sheet. Preserve panels 0,1,2,3 and7 exactly unchanged. Replace only panels4,5,6 (row3 left, row3 right, row4 left). Keep the SAME man, identical teal jacket and yellow backpack, face, person scale and original body position from panel0 in all replacements. IMPORTANT all replaced panels must remain much closer in composition to panel0; do NOT crouch or sit or show his back. Panel4: original man standing and leaning forward very slightly, left hand now slightly reaching toward the mossy rock; remove the little wooden sign; preserve original right-half tree and rock backdrop as closely as possible. Panel5: original man standing, photographed from only about 10 degrees to the right of original viewpoint, still mostly facing camera, his face visible; preserve his scale and original forest setting; small perspective difference only. Panel6: original man standing with his free hand raised slightly, still facing camera with identical scale and teal jacket/yellow backpack; replace only surrounding forest backdrop with a nearby different leafy forest path, keeping its overall brightness and arrangement similar, omit sign. No other changes. Exactly two columns and four rows, equal square panels, no border, no labels, no gutters, photographic realism.
