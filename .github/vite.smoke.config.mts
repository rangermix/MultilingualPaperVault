import app from '../src/apps/web/vite.config';

// Never proxy an unmocked browser-test request to an installed library on :8080.
export default { ...app, server: { ...app.server, proxy: {} } };
