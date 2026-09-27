import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Landing from './pages/Landing.jsx';
import Login from './pages/Login.jsx';
import Complaint from './pages/Complaint.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/complaint" element={<Complaint />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
