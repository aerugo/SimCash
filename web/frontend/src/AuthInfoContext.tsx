import { createContext, useContext } from 'react';

export interface AuthInfo {
  isAdmin: boolean;
  userEmail: string;
  onSignOut: () => void;
}

export const AuthInfoContext = createContext<AuthInfo>({ isAdmin: false, userEmail: '', onSignOut: () => {} });

export function useAuthInfo() {
  return useContext(AuthInfoContext);
}
