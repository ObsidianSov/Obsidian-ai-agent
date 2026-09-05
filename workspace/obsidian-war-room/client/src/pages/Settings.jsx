import React, { useState } from 'react';
import { Download, Upload, Trash2, Database, Info } from 'lucide-react';

const API_URL = 'http://localhost:3001/api';

export default function SettingsPage() {
  const [exportStatus, setExportStatus] = useState('');
  const [importStatus, setImportStatus] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);

  const handleExport = async () => {
    try {
      setExportStatus('exporting');
      const res = await fetch(`${API_URL}/export`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `trading-journal-export-${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setExportStatus('success');
      setTimeout(() => setExportStatus(''), 3000);
    } catch (err) {
      console.error('Export failed:', err);
      setExportStatus('error');
      setTimeout(() => setExportStatus(''), 3000);
    }
  };

  const handleImport = async (e) => {
    e.preventDefault();
    if (!selectedFile) return;

    try {
      setImportStatus('importing');
      const formData = new FormData();
      formData.append('file', selectedFile);

      const res = await fetch(`${API_URL}/import`, {
        method: 'POST',
        body: formData
      });

      if (res.ok) {
        const data = await res.json();
        setImportStatus('success');
        setSelectedFile(null);
        alert(`Successfully imported ${data.imported} trades!`);
      } else {
        setImportStatus('error');
      }
      setTimeout(() => setImportStatus(''), 3000);
    } catch (err) {
      console.error('Import failed:', err);
      setImportStatus('error');
      setTimeout(() => setImportStatus(''), 3000);
    }
  };

  return (
    <div className="settings-page">
      {/* Account Section */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <h3 className="card-title">Account</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #00d4ff 0%, #0088aa 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '24px',
              fontWeight: 'bold',
              color: '#0a0e17'
            }}
          >
            T
          </div>
          <div>
            <h4 style={{ fontSize: '18px', marginBottom: '4px' }}>Trader</h4>
            <p className="text-muted" style={{ fontSize: '14px' }}>Local Account</p>
          </div>
        </div>
      </div>

      {/* Data Management */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <h3 className="card-title">Data Management</h3>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Export */}
          <div
            style={{
              padding: '20px',
              background: 'var(--bg-tertiary)',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '8px',
                  background: 'rgba(0, 212, 255, 0.1)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <Download size={24} style={{ color: '#00d4ff' }} />
              </div>
              <div>
                <h4 style={{ fontSize: '16px', marginBottom: '4px' }}>Export Data</h4>
                <p className="text-muted" style={{ fontSize: '13px' }}>
                  Download all your trades as a CSV file for backup or analysis
                </p>
              </div>
            </div>
            <button
              className="btn btn-secondary"
              onClick={handleExport}
              disabled={exportStatus === 'exporting'}
            >
              {exportStatus === 'exporting' ? 'Exporting...' :
               exportStatus === 'success' ? '✓ Exported' :
               exportStatus === 'error' ? 'Failed' : 'Export CSV'}
            </button>
          </div>

          {/* Import */}
          <div
            style={{
              padding: '20px',
              background: 'var(--bg-tertiary)',
              borderRadius: '8px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '8px',
                  background: 'rgba(16, 185, 129, 0.1)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <Upload size={24} style={{ color: '#10b981' }} />
              </div>
              <div>
                <h4 style={{ fontSize: '16px', marginBottom: '4px' }}>Import Data</h4>
                <p className="text-muted" style={{ fontSize: '13px' }}>
                  Import trades from a CSV file. Supported columns: symbol, side, entry_date, exit_date, entry_price, exit_price, quantity, strategy, notes
                </p>
              </div>
            </div>
            <form onSubmit={handleImport} style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setSelectedFile(e.target.files[0])}
                style={{ flex: 1 }}
              />
              <button
                type="submit"
                className="btn btn-primary"
                disabled={!selectedFile || importStatus === 'importing'}
              >
                {importStatus === 'importing' ? 'Importing...' :
                 importStatus === 'success' ? '✓ Imported' :
                 importStatus === 'error' ? 'Failed' : 'Import CSV'}
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Database Info */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <h3 className="card-title">Database</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '8px',
              background: 'rgba(139, 92, 246, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <Database size={24} style={{ color: '#8b5cf6' }} />
          </div>
          <div>
            <h4 style={{ fontSize: '16px', marginBottom: '4px' }}>SQLite Database</h4>
            <p className="text-muted" style={{ fontSize: '13px' }}>
              Local database stored at: server/trading.db
            </p>
          </div>
        </div>
      </div>

      {/* About */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">About</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '8px',
              background: 'rgba(0, 212, 255, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <Info size={24} style={{ color: '#00d4ff' }} />
          </div>
          <div>
            <h4 style={{ fontSize: '16px', marginBottom: '4px' }}>Obsidian War-Room</h4>
            <p className="text-muted" style={{ fontSize: '13px' }}>
              Version 1.0.0 • A tactical trading journal for serious traders
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
