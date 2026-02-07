import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { HomePage } from "./pages/HomePage";
import { DebatePage } from "./pages/DebatePage";
import { MetricsPage } from "./pages/MetricsPage";
import { HistoryPage } from "./pages/HistoryPage";
import { Layout } from "./components/Layout";
import "./styles/global.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/debate" element={<DebatePage />} />
          <Route path="/metrics" element={<MetricsPage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
