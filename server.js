const express = require('express');
const path = require('path');
const compression = require('compression');
const helmet = require('helmet');
const mongoose = require('mongoose');
const session = require('express-session');
// FIX 1: OLD STYLE IMPORT (Works with v3)
const MongoStore = require('connect-mongo')(session); 
const bcrypt = require('bcryptjs');

const app = express();
const PORT = process.env.PORT || 3000;

// --- 1. DATABASE CONNECTION ---
// Your Connection String
const DB_URI = "mongodb+srv://admin:Parth%40272006@admin.aylf3v1.mongodb.net/?appName=admin";

mongoose.connect(DB_URI)
  .then(() => console.log('✅ Connected to MongoDB Atlas'))
  .catch(err => console.error('❌ DB Connection Error:', err));

// --- 2. DATABASE MODELS ---
const userSchema = new mongoose.Schema({
  email: { type: String, required: true, unique: true },
  password: { type: String, required: true },
  name: { type: String, default: "User" },
  joinDate: { type: Date, default: Date.now }
});
const User = mongoose.model('User', userSchema);

const ratingSchema = new mongoose.Schema({
  toolName: { type: String, required: true, unique: true },
  votes: { type: Number, default: 0 },
  totalScore: { type: Number, default: 0 }
});
const Rating = mongoose.model('Rating', ratingSchema);

// --- 3. MIDDLEWARE ---
app.use(helmet({ contentSecurityPolicy: false }));
app.use(compression());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname)));

app.use(session({
  secret: 'my-super-secret-key-123',
  resave: false,
  saveUninitialized: false,
  // FIX 2: OLD STYLE USAGE (Works with v3)
  store: new MongoStore({ url: DB_URI }),
  cookie: { maxAge: 1000 * 60 * 60 * 24 }
}));

// --- 4. AUTH ROUTES ---
app.post('/api/register', async (req, res) => {
  try {
    const { name, email, password } = req.body;
    const existing = await User.findOne({ email });
    if (existing) return res.status(400).json({ error: "Email already taken" });
    const hashedPassword = await bcrypt.hash(password, 10);
    const user = new User({ name, email, password: hashedPassword });
    await user.save();
    req.session.userId = user._id;
    res.json({ success: true, message: "Account created!" });
  } catch (err) {
    res.status(500).json({ error: "Server error" });
  }
});

app.post('/api/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    const user = await User.findOne({ email });
    if (!user) return res.status(400).json({ error: "User not found" });
    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) return res.status(400).json({ error: "Invalid password" });
    req.session.userId = user._id;
    req.session.userName = user.name;
    res.json({ success: true, message: "Logged in successfully" });
  } catch (err) {
    res.status(500).json({ error: "Server error" });
  }
});

app.get('/api/me', (req, res) => {
  if (req.session.userId) {
    res.json({ loggedIn: true, name: req.session.userName });
  } else {
    res.json({ loggedIn: false });
  }
});

app.post('/api/logout', (req, res) => {
  req.session.destroy();
  res.json({ success: true });
});

// --- 5. RATING ROUTES ---
app.get('/api/rating/:tool', async (req, res) => {
  const toolName = req.params.tool;
  let data = await Rating.findOne({ toolName });
  if (!data) return res.json({ votes: 125, average: 4.8 });
  const average = (data.totalScore / data.votes).toFixed(1);
  res.json({ votes: data.votes, average: average });
});

app.post('/api/rate', async (req, res) => {
  const { toolName, stars } = req.body;
  let data = await Rating.findOne({ toolName });
  if (!data) data = new Rating({ toolName, votes: 120, totalScore: 576 });
  data.votes += 1;
  data.totalScore += stars;
  await data.save();
  const average = (data.totalScore / data.votes).toFixed(1);
  res.json({ success: true, votes: data.votes, average: average });
});

// --- NEW: USER PROFILE ROUTES ---

// 1. Get Full Profile Data
app.get('/api/user/profile', async (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: "Not logged in" });
  
  try {
    const user = await User.findById(req.session.userId).select('-password'); // Don't send password
    if (!user) return res.status(404).json({ error: "User not found" });
    res.json(user);
  } catch (err) {
    res.status(500).json({ error: "Server error" });
  }
});

// 2. Delete Account (Settings Feature)
app.post('/api/user/delete', async (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: "Not logged in" });

  try {
    await User.findByIdAndDelete(req.session.userId);
    req.session.destroy(); // Log them out
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: "Could not delete account" });
  }
});

// --- 6. START SERVER ---
app.listen(PORT, () => {
  console.log(`🚀 Server with Auth running at http://localhost:${PORT}`);
});