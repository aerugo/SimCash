import { createContext, useContext } from 'react';

export interface AuthInfo {
  isAdmin: boolean;
  userEmail: string;
  isGuest: boolean;
  onSignOut: () => void;
  onSignIn: () => Promise<void>;
}

export const AuthInfoContext = createContext<AuthInfo>({
  isAdmin: false,
  userEmail: '',
  isGuest: true,
  onSignOut: () => {},
  onSignIn: async () => {},
});

export function useAuthInfo() {
  return useContext(AuthInfoContext);
}
