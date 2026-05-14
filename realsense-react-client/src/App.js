import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import WebRTCDemo from './pages/WebRTCDemo';
import PointCloudDemo from './pages/PointCloudDemo';
import ApiDocsPage from './pages/ApiDocsPage';
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <nav className="navbar">
          <div className="nav-container">
            <div className="nav-logo">
              <h1>🎯 RealSense Web Client</h1>
            </div>
            <div className="nav-links">
              <Link to="/" className="nav-link">WebRTC Demo</Link>
              <Link to="/pointcloud" className="nav-link">3D Point Cloud</Link>
              <Link to="/api-docs" className="nav-link">API Docs</Link>
            </div>
          </div>
        </nav>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<WebRTCDemo />} />
            <Route path="/pointcloud" element={<PointCloudDemo />} />
            <Route path="/api-docs" element={<ApiDocsPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
