import { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import Upload from './pages/Upload';
import ParseView from './pages/ParseView';
import CompareView from './pages/CompareView';
import type { ParseResponse, CompareResponse } from './types/capability';
import './index.css';

function NavBar() {
    const loc = useLocation();
    return (
        <nav className="navbar">
            <Link to="/" className="nav-brand">
                <span className="nav-icon">📡</span>
                <span>UE Capability Parser</span>
            </Link>
            <div className="nav-links">
                <Link to="/" className={`nav-link ${loc.pathname === '/' ? 'active' : ''}`}>Upload</Link>
                <Link to="/parse" className={`nav-link ${loc.pathname === '/parse' ? 'active' : ''}`}>Parse</Link>
                <Link to="/compare" className={`nav-link ${loc.pathname === '/compare' ? 'active' : ''}`}>Compare</Link>
            </div>
        </nav>
    );
}

function App() {
    const [parseData, setParseData] = useState<ParseResponse | null>(null);
    const [compareData, setCompareData] = useState<CompareResponse | null>(null);

    return (
        <BrowserRouter>
            <NavBar />
            <main className="main-content">
                <Routes>
                    <Route
                        path="/"
                        element={
                            <Upload
                                onParsed={setParseData}
                                onCompared={setCompareData}
                            />
                        }
                    />
                    <Route path="/parse" element={<ParseView data={parseData} />} />
                    <Route path="/compare" element={<CompareView data={compareData} />} />
                </Routes>
            </main>
        </BrowserRouter>
    );
}

export default App;
