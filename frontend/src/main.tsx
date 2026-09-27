import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import AdminRegistrationPage from "./AdminRegistrationPage";
import App from "./App";
import RegistrationPage from "./RegistrationPage";

import "./styles.css";


function normalizePath(pathname: string): string {
  const normalized = pathname.replace(
    /\/+$/,
    "",
  );

  return normalized || "/";
}


function moveTo(path: string): void {
  window.location.href = path;
}


const currentPath = normalizePath(
  window.location.pathname,
);


function CurrentPage() {
  if (currentPath === "/register") {
    return (
      <RegistrationPage
        onBack={() => {
          moveTo("/");
        }}
      />
    );
  }

  if (currentPath === "/admin/registrations") {
    return (
      <AdminRegistrationPage
        onBack={() => {
          moveTo("/");
        }}
      />
    );
  }

  return <App />;
}


createRoot(
  document.getElementById("root")!,
).render(
  <StrictMode>
    <CurrentPage />
  </StrictMode>,
);