import { initializeApp } from 'firebase/app';
import {
  getAuth,
  signInWithPopup,
  // signInWithRedirect,
  getRedirectResult,
  signInWithEmailAndPassword as fbSignInWithEmailAndPassword,
  updatePassword as fbUpdatePassword,
  reauthenticateWithCredential,
  EmailAuthProvider,
  GoogleAuthProvider,
  signOut as fbSignOut,
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
  // Use popup everywhere — redirect flow has cross-domain issues with
  // authDomain (firebaseapp.com) vs hosting domain (web.app)
  const result = await signInWithPopup(auth, googleProvider);
  return result.user;
}

// Call on app init to complete redirect sign-in if returning from Google
export async function handleRedirectResult(): Promise<User | null> {
  const result = await getRedirectResult(auth);
  return result?.user ?? null;
}

export async function signOut(): Promise<void> {
  await fbSignOut(auth);
}

export async function getIdToken(): Promise<string | null> {
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken();
}

// ---- Email + Password sign-in ----

export async function signInWithPassword(email: string, password: string): Promise<User> {
  const result = await fbSignInWithEmailAndPassword(auth, email, password);
  return result.user;
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const user = auth.currentUser;
  if (!user || !user.email) throw new Error('No authenticated user.');
  const credential = EmailAuthProvider.credential(user.email, currentPassword);
  await reauthenticateWithCredential(user, credential);
  await fbUpdatePassword(user, newPassword);
}
