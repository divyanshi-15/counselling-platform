import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";
import { Layout } from "@/components/Layout";
import { AuthProvider } from "@/lib/auth";
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import PracticePage from "@/pages/PracticePage";
import RoleHome from "@/pages/RoleHome";
import ClientDashboard from "@/pages/client/Dashboard";
import Book from "@/pages/client/Book";
import Intake from "@/pages/client/Intake";
import Exercise from "@/pages/client/Exercise";
import Session from "@/pages/client/Session";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/p/:slug" element={<PracticePage />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/client" element={<ClientDashboard />} />
            <Route path="/client/book/:therapistId" element={<Book />} />
            <Route path="/client/intake/:bookingId" element={<Intake />} />
            <Route path="/client/exercise/:assignmentId" element={<Exercise />} />
            <Route path="/client/session/:bookingId" element={<Session />} />
            {["therapist", "owner", "admin"].map((r) => <Route key={r} path={`/${r}`} element={<RoleHome />} />)}
            <Route path="*" element={<p>Page not found.</p>} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
