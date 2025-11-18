# sLLM Frontend

Vue 3 frontend application for the Slime Mould Monitor, built with Vite.

## Development

### Prerequisites

- Node.js 18+ and npm

### Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The dev server will run on `http://localhost:5173` with hot module replacement.

### Build for Production

```bash
# Build the application
npm run build
```

This creates an optimized production build in the `dist/` directory.

### Preview Production Build

```bash
# Preview the production build locally
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── App.vue          # Main Vue component (Options API)
│   ├── main.js          # Application entry point
│   └── style.css        # Global styles
├── index.html           # HTML template
├── package.json         # Dependencies and scripts
├── vite.config.js       # Vite configuration
└── dist/                # Production build output (gitignored)
```

## Dependencies

- **Vue 3** - Progressive JavaScript framework
- **Vite** - Build tool and dev server
- **Chart.js** - Charting library for electrical readings
- **Axios** - HTTP client for API requests
- **Socket.IO Client** - Real-time WebSocket communication

## Deployment

The deployment script (`scripts/deploy.sh`) automatically:
1. Installs npm dependencies
2. Builds the frontend with Vite
3. Copies the built files to `/var/www/sllm/frontend/`

No manual build step is required when deploying.

