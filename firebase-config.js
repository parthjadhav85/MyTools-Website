import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { 
  getAuth, 
  GoogleAuthProvider, 
  signInWithPopup, 
  createUserWithEmailAndPassword, // <--- NEW
  signInWithEmailAndPassword,     // <--- NEW
  signOut, 
  onAuthStateChanged 
} from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";
import { getFirestore, doc, setDoc, getDoc, updateDoc, arrayUnion } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";

// --- PASTE YOUR REAL FIREBASE CONFIG HERE ---
const firebaseConfig = {
  apiKey: "AIzaSyDAUfxdjTEKwlOsgncsclVNRjXA_H8WpQo",
  authDomain: "mytools-01.firebaseapp.com",
  projectId: "mytools-01",
  storageBucket: "mytools-01.firebasestorage.app",
  messagingSenderId: "324296339754",
  appId: "1:324296339754:web:d5ee066f7511f83864ae53",
  measurementId: "G-19JHWW41WJ"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const provider = new GoogleAuthProvider();

export { auth, db, provider, signInWithPopup, createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut, onAuthStateChanged, doc, setDoc, getDoc, updateDoc, arrayUnion };