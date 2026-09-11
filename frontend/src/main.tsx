import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";
ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);

// 개발 서버(vite dev)는 모듈이 요청마다 바뀌므로 캐시를 등록하면 오래된 화면이 보일 수 있다.
// 프로덕션 빌드(npm run build 결과물)를 서빙할 때만 서비스워커를 등록한다.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

