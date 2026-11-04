import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { SiteLayout } from "./components/Site";
import Home from "./pages/Home";
import { About, Contact, Doctors, Insurance, Specialities, Visitors } from "./pages/Public";
import { Accept, Login, Signup } from "./pages/Auth";
import { Appointments, Overview, Profile, Reports, Waitlist } from "./pages/Portal";
import { Book } from "./pages/Book";
import { Dashboard, Pay } from "./pages/Dashboard";
import { Architecture } from "./pages/Architecture";
import { Checkin } from "./pages/Checkin";
import { Assistant } from "./pages/Assistant";
import { Policies } from "./pages/Policies";
import { Admin } from "./pages/Admin";
import { loadChat } from "./lib/chat";

function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    const l = (window as any).__lenis;
    if (l) l.scrollTo(0, { immediate: true }); else window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

export default function App() {
  const { pathname } = useLocation();
  // The patient chat belongs on the patient-facing site, not on the staff console. loadChat() is idempotent,
  // so calling it again after navigating back out of /admin is safe.
  useEffect(() => { if (!pathname.startsWith("/admin")) loadChat(); }, [pathname]);
  return (
    <>
      <ScrollTop />
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/admin/*" element={<Admin />} />
        <Route path="*" element={
          <SiteLayout>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/doctors" element={<Doctors />} />
              <Route path="/assistant" element={<Assistant />} />
              <Route path="/policies" element={<Policies />} />
              <Route path="/departments" element={<Specialities />} />
              <Route path="/about" element={<About />} />
              <Route path="/specialities" element={<Specialities />} />
              <Route path="/visitors" element={<Visitors />} />
              <Route path="/insurance" element={<Insurance />} />
              <Route path="/contact" element={<Contact />} />
              <Route path="/login" element={<Login />} />
              <Route path="/signup" element={<Signup />} />
              <Route path="/portal" element={<Overview />} />
              <Route path="/portal/book" element={<Book />} />
              <Route path="/portal/appointments" element={<Appointments />} />
              <Route path="/portal/reports" element={<Reports />} />
              <Route path="/portal/waitlist" element={<Waitlist />} />
              <Route path="/portal/profile" element={<Profile />} />
              <Route path="/waitlist/accept" element={<Accept />} />
              <Route path="/pay" element={<Pay />} />
              <Route path="/architecture" element={<Architecture />} />
              <Route path="/checkin" element={<Checkin />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </SiteLayout>
        } />
      </Routes>
    </>
  );
}
