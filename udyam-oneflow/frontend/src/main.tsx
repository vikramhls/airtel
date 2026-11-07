import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import { I18nProvider } from "./i18n";
import Advise from "./pages/Advise";
import Home from "./pages/Home";
import Kyc from "./pages/Kyc";
import Partner from "./pages/Partner";
import Plan from "./pages/Plan";
import QuotePage from "./pages/QuotePage";
import Track from "./pages/Track";
import { useFlow } from "./hooks/useSession";

function TrackLatest() {
  const { flow } = useFlow();
  return flow.orderId ? <Navigate to={`/track/${flow.orderId}`} replace /> : <Navigate to="/kyc" replace />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <I18nProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/advise" element={<Advise />} />
          <Route path="/plan" element={<Plan />} />
          <Route path="/quote" element={<QuotePage />} />
          <Route path="/consent" element={<Navigate to="/kyc" replace />} />
          <Route path="/kyc" element={<Kyc />} />
          <Route path="/track" element={<TrackLatest />} />
          <Route path="/track/:orderId" element={<Track />} />
          <Route path="/partner" element={<Partner />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </I18nProvider>
  </React.StrictMode>,
);
