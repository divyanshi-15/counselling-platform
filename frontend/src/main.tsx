import Availability from "./pages/therapist/Availability";
import TherapistProfilePage from "./pages/therapist/Profile";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";
import { Layout } from "@/components/Layout";
import { AuthProvider } from "@/lib/auth";
import Home from "@/pages/Home";
import Directory from "@/pages/Directory";
import TherapistProfile from "@/pages/TherapistProfile";
import Legal from "@/pages/Legal";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import PracticePage from "@/pages/PracticePage";
import Owner from "@/pages/owner/Owner";
import PracticeSetup from "@/pages/owner/Setup";
import Invitation from "@/pages/therapist/Invitation";
import Admin from "@/pages/admin/Admin";
import ClientDashboard from "@/pages/client/Dashboard";
import Book from "@/pages/client/Book";
import Intake from "@/pages/client/Intake";
import Exercise from "@/pages/client/Exercise";
import BrainDump from "@/pages/client/BrainDump";
import Session from "@/pages/client/Session";
import Today from "@/pages/therapist/Today";
import Inbox from "@/pages/therapist/Inbox";
import Activity from "@/pages/therapist/Activity";
import Bookings from "@/pages/therapist/Bookings";
import BookingDetail from "@/pages/therapist/BookingDetail";
import TherapistClient from "@/pages/therapist/Client";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/privacy" element={<Legal />} />
            <Route path="/terms" element={<Legal />} />
            <Route path="/safety" element={<Legal />} />
            <Route path="/directory" element={<Directory />} />
            <Route path="/therapists/:id" element={<TherapistProfile />} />
            <Route path="/p/:slug" element={<PracticePage />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/client" element={<ClientDashboard />} />
            <Route path="/client/book/:therapistId" element={<Book />} />
            <Route path="/client/intake/:bookingId" element={<Intake />} />
            <Route path="/client/exercise/:assignmentId" element={<Exercise />} />
            <Route path="/client/brain-dump" element={<BrainDump />} />
            <Route path="/client/session/:bookingId" element={<Session />} />
            <Route path="/therapist" element={<Today />} />
            <Route path="/therapist/inbox" element={<Inbox />} />
            <Route path="/therapist/activity" element={<Activity />} />
            <Route path="/therapist/availability" element={<Availability />} />
            <Route path="/therapist/profile" element={<TherapistProfilePage />} />
            <Route path="/therapist/bookings" element={<Bookings />} />
            <Route path="/therapist/bookings/:bookingId" element={<BookingDetail />} />
            <Route path="/therapist/clients/:clientId" element={<TherapistClient />} />
            <Route path="/owner" element={<Owner />} />
            <Route path="/owner/setup/:id" element={<PracticeSetup />} />
            <Route path="/invitation" element={<Invitation />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="*" element={<p>Page not found.</p>} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
