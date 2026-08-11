import { useState, useEffect } from "react";
import { compareApi } from "../services/api";

export function useNotifications() {
  const [unreadNotifications, setUnreadNotifications] = useState<number>(0);
  const [recentErrors, setRecentErrors] = useState<any[]>([]);
  const [showNotifications, setShowNotifications] = useState<boolean>(false);

  const fetchRecentErrors = async () => {
    try {
      const response = await compareApi.getAutomationLogs(0, 10, undefined, true);
      if (response && response.results) {
        setRecentErrors(response.results);
        
        const lastReadIdStr = localStorage.getItem("cradle_last_read_error_id");
        const lastReadId = lastReadIdStr ? parseInt(lastReadIdStr, 10) : 0;
        
        const newUnread = response.results.filter((log: any) => log.id > lastReadId).length;
        setUnreadNotifications(newUnread);
      }
    } catch (error) {
      console.error("Failed to fetch recent errors for notifications:", error);
    }
  };

  useEffect(() => {
    fetchRecentErrors();
    
    const interval = setInterval(fetchRecentErrors, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleNotifications = () => {
    setShowNotifications(prev => {
      const nextState = !prev;
      if (nextState && recentErrors.length > 0) {
        const maxId = Math.max(...recentErrors.map(log => log.id));
        localStorage.setItem("cradle_last_read_error_id", maxId.toString());
        setUnreadNotifications(0);
      }
      return nextState;
    });
  };

  useEffect(() => {
    if (!showNotifications) return;
    
    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest(".notifications-container")) {
        setShowNotifications(false);
      }
    };
    
    document.addEventListener("click", handleOutsideClick);
    return () => document.removeEventListener("click", handleOutsideClick);
  }, [showNotifications]);

  return {
    unreadNotifications,
    recentErrors,
    showNotifications,
    setShowNotifications,
    handleToggleNotifications
  };
}
