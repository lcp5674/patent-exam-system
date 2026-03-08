import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { User } from "../../types";

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isValidated: boolean;
}

const initialState: AuthState = {
  user: null,
  token: (() => {
    const token = localStorage.getItem("access_token");
    // 确保token不为空字符串
    return token && token.trim() !== "" ? token : null;
  })(),
  isAuthenticated: (() => {
    const token = localStorage.getItem("access_token");
    return !!(token && token.trim() !== "");
  })(),
  isValidated: false,
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setCredentials(state, action: PayloadAction<{ user: User; token: string }>) {
      state.user = action.payload.user;
      state.token = action.payload.token;
      state.isAuthenticated = true;
      state.isValidated = true;
      localStorage.setItem("access_token", action.payload.token);
    },
    setValidated(state, action: PayloadAction<boolean>) {
      state.isValidated = action.payload;
    },
    logout(state) {
      state.user = null;
      state.token = null;
      state.isAuthenticated = false;
      state.isValidated = false;
      localStorage.removeItem("access_token");
    },
  },
});

export const { setCredentials, setValidated, logout } = authSlice.actions;
export default authSlice.reducer;
