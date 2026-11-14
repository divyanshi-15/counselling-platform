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
            {["client", "therapist", "owner", "admin"].map((r) => <Route key={r} path={`/${r}`} element={<RoleHome />} />)}
            <Route path="*" element={<p>Page not found.</p>} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
