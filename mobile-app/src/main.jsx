import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';
import { registerSW } from 'virtual:pwa-register';

// Register Service Worker for offline PWA app-shell caching
const updateSW = registerSW({
  onNeedRefresh() {},
  onOfflineReady() {
    console.log('Vigil Capture PWA is ready for offline use in airplane mode.');
  },
});

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
