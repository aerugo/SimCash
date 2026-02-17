import { initializeApp } from 'firebase/app';
import {
  getAuth,
  signInWithPopup,
  GoogleAuthProvider,
  signOut as fbSignOut,
  type User,
} from 'firebase/auth';

const firebaseConfig = {
  apiKey: 'AIzaSyAT_IULl1kAW804XTIhoLhASDXIlv21Kas',
  authDomain: 'simcash-487714.firebaseapp.com',
  projectId: 'simcash-487714',
  storageBucket: 'simcash-487714.firebasestorage.app',
  messagingSenderId: '997004209370',
  appId: '1:997004209370:web:bc69475748ca89ceb289e3',
  measurementId: 'G-FQ44MJ91Q3',
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
