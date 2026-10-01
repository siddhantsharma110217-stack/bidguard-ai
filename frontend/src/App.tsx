import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { DemoProvider } from './context/DemoContext'
import { EvaluationProvider } from './context/EvaluationContext'
import { DashboardPage } from './pages/DashboardPage'
import { TenderPage } from './pages/TenderPage'
import { RequirementsPage } from './pages/RequirementsPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { EvaluationPage } from './pages/EvaluationPage'
import { CompliancePage } from './pages/CompliancePage'
import { ReportsPage } from './pages/ReportsPage'
import { AuditPage } from './pages/AuditPage'

function App() {
  return (
    <BrowserRouter>
      <DemoProvider>
        <EvaluationProvider>
          <AppShell>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/tender" element={<TenderPage />} />
              <Route path="/requirements" element={<RequirementsPage />} />
              <Route path="/documents" element={<DocumentsPage />} />
              <Route path="/evaluation" element={<EvaluationPage />} />
              <Route path="/compliance" element={<CompliancePage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/audit" element={<AuditPage />} />
            </Routes>
          </AppShell>
        </EvaluationProvider>
      </DemoProvider>
    </BrowserRouter>
  )
}

export default App
