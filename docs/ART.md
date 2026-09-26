# Patient art

Each patient's scene is an original flat-vector SVG built from layers
(`web/src/art/PatientScene.tsx`):

- **room**: the window sky follows the stage (day, dusk, night, sunny when
  cured) and a wall monitor shows a live ECG;
- **furniture**: a bedside table with a personal prop (Walter's honey jar,
  Mia's rabbit Clover and her brother's drawing), the IV pole, the bed;
- **patient**: skin tone drains toward pale as the stage worsens, and the
  eyes, brows and mouth change with the stage; breathing follows the
  respiratory rate and the eyes blink;
- **overlays**, one per trait `overlay` key in `illnesses/*.yaml`:

  | key | shows | | key | shows |
  |---|---|---|---|---|
  | `cough` | cough puffs | | `raccoon_eyes` | dark rings around the eyes |
  | `tired` | heavy eyelids | | `ptosis` | one drooping eyelid |
  | `wince` | furrowed brows | | `dancing_eyes` | jittering pupils |
  | `cannula` | nasal oxygen tubing | | `flushed` | red cheeks |
  | `tissue` | blood-spotted tissue | | `pale` | extra pallor |
  | `thin`, `cachexia` | hollow cheeks | | `spots` | bluish skin nodules |
  | `drain` | chest drain + bottle | | `belly` | swollen abdomen under the blanket |
  | `face_swelling` | puffy face | | `brace` | neck brace |
  | `headwrap` | head bandage | | `iv` | second IV bag, faster drip |
  | `jaundice` | yellow skin and eyes | | `haze` | smog outside the window |

  and for patient events:

  | key | shows | | key | shows |
  |---|---|---|---|---|
  | `cigarettes` | a pack hidden on the windowsill | | `crayons` | crayons on the blanket |
  | `pills` | an untouched pill cup | | `glitter` | twinkling glitter everywhere |
  | `plaster` | plaster on the forehead | | `isolation` | "protective isolation" sign |
  | `chicken` | fried-chicken bucket on the floor | | `sticker` | gold-star sticker on the hand |
  | `bee` | a bee buzzing by the window | | `snow` | snowstorm outside |
  | `clover_missing` | Mia's rabbit is gone (in the laundry) | | | |

  At the **critical** stage the patient wears an oxygen mask and the monitor
  alarms. At **cured**, the room is sunny with balloons and a get-well card.
  At **deceased**, the scene is quiet: night, a flatline, a flower, and no
  symptom overlays.

## Using your own art

Put images in `web/public/art/<patient>/` and name them in that folder's
`manifest.json`. Any entry left empty falls back to the built-in SVG.

```json
{
  "scene": {
    "default": "room.png",
    "critical": "room-icu.png",
    "cured": "discharge.png"
  },
  "overlays": {
    "cannula": "cannula.png",
    "raccoon_eyes": "raccoon.png"
  }
}
```

- `scene.<stage>` replaces the whole scene for that stage, and
  `scene.default` covers every stage without its own image. Stages are
  `stable`, `symptomatic`, `serious`, `critical`, `deceased` and `cured`.
- `overlays.<key>` images are stacked on top of the scene, so use
  transparent PNG or SVG at the same size. If you supply an overlay, the
  built-in version of that overlay is switched off.
- Aim for a 4:3 canvas (the built-in scene is 480×360).

Rebuild the image (`docker compose build seurat`) or run `npm run build` in
`web/` to pick up new files. `web/tests/unit.test.ts` covers how the manifest
is resolved.
