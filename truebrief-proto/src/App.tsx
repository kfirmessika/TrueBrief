import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import TopicList from './pages/TopicList'
import Dashboard from './pages/Dashboard'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/topics" element={<TopicList />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}

export default App
