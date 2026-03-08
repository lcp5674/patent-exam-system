import { Routes, Route, Navigate } from "react-router-dom";
import { useSelector, useDispatch } from "react-redux";
import type { RootState } from "./store";
import { logout } from "./store/slices/authSlice";
import { useEffect } from "react";
import api from "./services/api";
import AppLayout from "./components/layout/AppLayout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import PatentList from "./pages/PatentList";
import PatentDetail from "./pages/PatentDetail";
import ExaminationWorkspace from "./pages/ExaminationWorkspace";
import ExaminationDashboard from "./pages/ExaminationDashboard";
import RuleEngine from "./pages/RuleEngine";
import AIAssistant from "./pages/AIAssistant";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";
import UserManagement from "./pages/UserManagement";
import TenantManagement from "./pages/TenantManagement";
import Workflow from "./pages/Workflow";
import RAGManagement from "./pages/RAGManagement";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuth = useSelector((s: RootState) => s.auth.isAuthenticated);
  return isAuth ? <>{children}</> : <Navigate to="/login" />;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const user = useSelector((s: RootState) => s.auth.user);
  return (user?.role === "admin") ? <>{children}</> : <Navigate to="/" />;
}

function AuthValidator({ children }: { children: React.ReactNode }) {
  const dispatch = useDispatch();
  const token = useSelector((s: RootState) => s.auth.token);
  const isValidated = useSelector((s: RootState) => s.auth.isValidated);
  const user = useSelector((s: RootState) => s.auth.user);

  useEffect(() => {
    if (token && !isValidated) {
      api.get("/users/me")
        .then((res) => {
          if (res.data?.code === 200 || res.data?.id) {
            // Store user data if returned
            const userData = res.data?.data || res.data;
            if (userData?.id) {
              dispatch({ type: "auth/setCredentials", payload: { user: userData, token } });
            } else {
              dispatch({ type: "auth/setValidated", payload: true });
            }
          }
        })
        .catch(() => {
          dispatch(logout());
        });
    }
  }, [token, isValidated, dispatch]);

  return <>{children}</>;
}

export default function App() {
  return (
    <AuthValidator>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<PrivateRoute><AppLayout /></PrivateRoute>}>
          <Route index element={<Dashboard />} />
          <Route path="patents" element={<PatentList />} />
          <Route path="patents/:id" element={<PatentDetail />} />
          <Route path="examination/:id" element={<ExaminationWorkspace />} />
          <Route path="examination-dashboard" element={<ExaminationDashboard />} />
          <Route path="examination" element={<Navigate to="/patents" replace />} />
          <Route path="rules" element={<RuleEngine />} />
          <Route path="ai" element={<AIAssistant />} />
          <Route path="reports" element={<Reports />} />
          <Route path="settings" element={<Settings />} />
          <Route path="users" element={<AdminRoute><UserManagement /></AdminRoute>} />
          <Route path="tenants" element={<AdminRoute><TenantManagement /></AdminRoute>} />
          <Route path="workflow" element={<Workflow />} />
          <Route path="rag" element={<RAGManagement />} />
        </Route>
      </Routes>
    </AuthValidator>
  );
}
