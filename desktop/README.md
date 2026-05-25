# LectureLens Desktop

## Run locally

```powershell
cd desktop
npm install
npm run dev
```

## Notes

- The app listens for extension messages on `ws://localhost:27182`.
- The Python engine is a stub process for now (see `python/engine.py`).
- Model downloads are simulated and stored in your user data folder.

## Env

Optional:
- `LECTURELENS_WEB_APP_URL` (default: `http://localhost:3000`)
