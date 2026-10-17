// 답변 북마크. 브라우저(localStorage)에만 저장하며 서버와는 무관하다.
import { useEffect, useState } from "react";

import { BOOKMARK_STORAGE_KEY } from "../constants";

export function useBookmarks() {
  const [bookmarks, setBookmarks] = useState<number[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(BOOKMARK_STORAGE_KEY) || "[]");
    } catch {
      return [];
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(BOOKMARK_STORAGE_KEY, JSON.stringify(bookmarks));
    } catch {
      /* 저장소를 쓸 수 없는 환경은 무시 */
    }
  }, [bookmarks]);

  function toggleBookmark(messageId: number) {
    setBookmarks(prev => (prev.includes(messageId) ? prev.filter(id => id !== messageId) : [...prev, messageId]));
  }

  return { bookmarks, toggleBookmark };
}
