import React, { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [healthStatus, setHealthStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/health")
      .then((res) => res.json())
      .then((data) => {
        setHealthStatus(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch health status:", err);
        setLoading(false);
      });
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>🚗 AI Automotive Service Scheduler</h1>
        <p>Admin Dashboard</p>
      </header>

      <main className="App-main">
        <section className="status-card">
          <h2>System Status</h2>
          {loading ? (
            <p>Loading...</p>
          ) : healthStatus ? (
            <div className="status-ok">
              <span className="status-indicator">●</span>
              <span>Service: {healthStatus.service}</span>
              <span>Status: {healthStatus.status}</span>
            </div>
          ) : (
            <div className="status-error">
              <span className="status-indicator">●</span>
              <span>Service: Offline</span>
            </div>
          )}
        </section>

        <section className="features">
          <div className="feature-card">
            <h3>📞 Call Management</h3>
            <p>View and manage inbound/outbound calls</p>
            <button disabled>Coming Soon</button>
          </div>

          <div className="feature-card">
            <h3>📅 Appointments</h3>
            <p>Manage service appointments and calendar</p>
            <button disabled>Coming Soon</button>
          </div>

          <div className="feature-card">
            <h3>👥 Customers</h3>
            <p>Customer and vehicle information</p>
            <button disabled>Coming Soon</button>
          </div>

          <div className="feature-card">
            <h3>📊 Analytics</h3>
            <p>Call metrics and performance insights</p>
            <button disabled>Coming Soon</button>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
