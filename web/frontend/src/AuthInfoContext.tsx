import { createContext, useContext } from 'react';

export interface AuthInfo {
  isAdmin: boolean;
  userEmail: string;
  isGuest: boolean;
  onSignOut: () => void;
  onSignIn: () => Promise<void>;
  impersonatingUid: string | null;
  impersonatingEmail: string | null;
  setImpersonating: (uid: string | null, email: string | null) => void;
}

export const AuthInfoContext = createContext<AuthInfo>({
  isAdmin: false,
  userEmail: '',
  isGuest: true,
  onSignOut: () => {},
  onSignIn: async () => {},
  impersonatingUid: null,
  impersonatingEmail: null,
  setImpersonating: () => {},
});

export function useAuthInfo() {
  return useContext(AuthInfoContext);
}
