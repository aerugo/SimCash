import { initializeApp } from 'firebase/app';
import {
  getAuth,
  signInWithPopup,
  GoogleAuthProvider,
  signOut as fbSignOut,
  sendSignInLinkToEmail as fbSendSignInLinkToEmail,
  isSignInWithEmailLink as fbIsSignInWithEmailLink,
  signInWithEmailLink as fbSignInWithEmailLink,
  type User,
} from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY ?? '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ?? 'simcash-487714.firebaseapp.com',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID ?? 'simcash-487714',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET ?? 'simcash-487714.firebasestorage.app',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID ?? '997004209370',
  appId: import.meta.env.VITE_FIREBASE_APP_ID ?? '',
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID ?? '',
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

const googleProvider = new GoogleAuthProvider();

export async function signInWithGoogle(): Promise<User> {
  const result = await signInWithPopup(auth, googleProvider);
  return result.user;
}

export async function signOut(): Promise<void> {
  await fbSignOut(auth);
}

export async function getIdToken(): Promise<string | null> {
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken();
}

// ---- Magic Link (Email Link) sign-in ----

const EMAIL_STORAGE_KEY = 'simcash_signin_email';

export async function sendMagicLink(email: string): Promise<void> {
  const actionCodeSettings = {
    url: window.location.origin,
    handleCodeInApp: true,
  };
  await fbSendSignInLinkToEmail(auth, email, actionCodeSettings);
  window.localStorage.setItem(EMAIL_STORAGE_KEY, email);
}

export function isEmailSignInLink(url: string): boolean {
  return fbIsSignInWithEmailLink(auth, url);
}

export async function completeMagicLinkSignIn(url: string): Promise<User> {
  let email = window.localStorage.getItem(EMAIL_STORAGE_KEY);
  if (!email) {
    email = window.prompt('Please enter your email to complete sign-in:');
    if (!email) throw new Error('Email is required to complete sign-in.');
  }
  const result = await fbSignInWithEmailLink(auth, email, url);
  window.localStorage.removeItem(EMAIL_STORAGE_KEY);
  return result.user;
}
