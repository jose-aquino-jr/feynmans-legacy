# Angular frontend

See the [main README](../README.md) to prepare the datasets and start FastAPI before opening the API-backed map.

From this directory, install the locked dependencies and start the development server:

```bash
npm ci
npm start
```

Open [http://localhost:4200](http://localhost:4200). When `proxy.conf.json` is present and configured in `angular.json`, the development server forwards `/api` requests to FastAPI at `127.0.0.1:8000`.

## Build and test

```bash
npm test -- --watch=false
npm run build
```

The build writes the production files under `dist/`. Vitest runs the unit tests. For deployment, route `/api` to FastAPI on the same origin that serves the frontend.

Use the local CLI through `npm exec -- ng generate component component-name` to scaffold a component. See the [Angular CLI reference](https://angular.dev/tools/cli) for other commands.
