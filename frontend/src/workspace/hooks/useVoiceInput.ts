// 브라우저 음성 인식(Web Speech API)으로 입력창에 글을 받아 적는다.
// 인식된 확정 문장은 setInput으로 입력창 끝에 이어 붙이고, 오류는 setError로 알린다.
import { Dispatch, SetStateAction, useEffect, useRef, useState } from "react";

export function useVoiceInput(
  setInput: Dispatch<SetStateAction<string>>,
  setError: Dispatch<SetStateAction<string>>,
) {
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  function toggleVoiceInput() {
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognitionAPI) {
      setError("이 브라우저에서는 음성 입력을 지원하지 않습니다. Chrome 또는 Edge를 사용해 주세요.");
      return;
    }

    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }

    const recognition = new SpeechRecognitionAPI();
    recognition.lang = "ko-KR";
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onstart = () => {
      setIsListening(true);
      setError("");
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) finalText += event.results[i][0].transcript;
      }
      if (finalText.trim()) {
        setInput(prev => prev + (prev.trim() ? " " : "") + finalText.trim());
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      setIsListening(false);
      if (event.error === "not-allowed") {
        setError("마이크 권한이 필요합니다. 브라우저에서 마이크 사용을 허용해 주세요.");
      } else {
        setError(`음성 인식 오류: ${event.error}`);
      }
    };

    recognition.onend = () => setIsListening(false);

    recognitionRef.current = recognition;
    recognition.start();
  }

  // 로그아웃 등으로 화면이 사라질 때 마이크가 켜진 채 남지 않도록 정리
  useEffect(() => {
    return () => recognitionRef.current?.abort();
  }, []);

  return { isListening, toggleVoiceInput };
}
