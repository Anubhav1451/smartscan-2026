import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Lock, Mail, ArrowRight, ShieldCheck, AlertCircle, Loader2, ArrowLeft, CheckCircle2 } from 'lucide-react';

export default function LoginScreen({ onNavigate }) {
  const { 
    signIn, 
    signInWithGoogle, 
    resetPasswordForEmail, 
    signInDemo, 
    signInStaffDemo, 
    signInManagerDemo, 
    signInStyleHubManagerDemo 
  } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [error, setError] = useState('');

  // Forgot password state
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [resetEmail, setResetEmail] = useState('');
  const [resetLoading, setResetLoading] = useState(false);
  const [resetSuccess, setResetSuccess] = useState(false);
  const [resetError, setResetError] = useState('');

  const handleSignIn = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please enter both email and password.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await signIn(email, password);
    } catch (err) {
      setError(err.message || 'Invalid email or password.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError('');
    setGoogleLoading(true);
    try {
      await signInWithGoogle();
    } catch (err) {
      setError(err.message || 'Google sign-in initialization failed.');
      setGoogleLoading(false);
    }
  };

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    if (!resetEmail) {
      setResetError('Please enter your email address.');
      return;
    }
    setResetError('');
    setResetLoading(true);
    try {
      await resetPasswordForEmail(resetEmail);
      setResetSuccess(true);
    } catch (err) {
      setResetError(err.message || 'Failed to send password reset link. Please try again.');
    } finally {
      setResetLoading(false);
    }
  };

  const handleDemoSignIn = async () => {
    setError('');
    setDemoLoading(true);
    try {
      await signInDemo();
    } catch (err) {
      setError(err.message || 'Demo login failed.');
    } finally {
      setDemoLoading(false);
    }
  };

  const handleStaffDemo = async () => {
    setError('');
    setDemoLoading(true);
    try {
      await signInStaffDemo();
    } catch (err) {
      setError(err.message || 'Staff login failed.');
    } finally {
      setDemoLoading(false);
    }
  };

  const handleManagerDemo = async () => {
    setError('');
    setDemoLoading(true);
    try {
      await signInManagerDemo();
    } catch (err) {
      setError(err.message || 'Manager login failed.');
    } finally {
      setDemoLoading(false);
    }
  };

  const handleStyleHubManagerDemo = async () => {
    setError('');
    setDemoLoading(true);
    try {
      await signInStyleHubManagerDemo();
    } catch (err) {
      setError(err.message || 'StyleHub Manager login failed.');
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-between px-6 py-8 overflow-y-auto bg-cream">
      {/* Brand & Header */}
      <div className="flex flex-col items-center text-center mt-3">
        <div className="w-14 h-14 bg-primary rounded-2xl flex items-center justify-center shadow-md mb-2.5 p-2.5">
          {/* Locked SVG Brand Logo */}
          <svg viewBox="0 0 48 48" fill="none" className="w-9 h-9 text-cream" xmlns="http://www.w3.org/2000/svg">
            <path d="M14 16V12C14 6.47715 18.4772 2 24 2C29.5228 2 34 6.47715 34 12V16" stroke="#F6F2E7" strokeWidth="4" strokeLinecap="round"/>
            <rect x="6" y="14" width="36" height="30" rx="6" fill="#14532D" stroke="#F6F2E7" strokeWidth="3"/>
            <path d="M16 29L22 35L33 21" stroke="#F6F2E7" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <h1 className="text-xl font-bold text-ink tracking-tight">SmartScan</h1>
        <p className="text-ink-muted text-xs font-medium">Scan. Pay. Walk Out.</p>
        <span className="text-[10px] font-semibold text-primary uppercase tracking-wider bg-surface-tint px-2.5 py-0.5 rounded-full mt-1.5">
          Multi-Retailer Scan-and-Go
        </span>
      </div>

      {/* Main Content Area */}
      <div className="w-full max-w-sm mx-auto my-6">
        {showForgotPassword ? (
          /* Forgot Password View */
          <div className="bg-white rounded-card p-6 border border-surface-tint shadow-xs space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="space-y-1">
              <h3 className="font-bold text-sm text-ink">Reset password</h3>
              <p className="text-xs text-ink-muted leading-relaxed">
                Enter your account email and we'll send you a password recovery link.
              </p>
            </div>

            {resetSuccess ? (
              <div className="space-y-4 pt-2">
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-card-sm flex items-start gap-2.5 text-emerald-800 text-xs">
                  <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5 text-emerald-600" />
                  <span>Password reset link sent! Check your email inbox for instructions.</span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setShowForgotPassword(false);
                    setResetSuccess(false);
                    setResetError('');
                  }}
                  className="w-full py-3 bg-primary hover:bg-primary-dark text-white font-semibold rounded-card shadow-sm flex items-center justify-center gap-2 transition text-xs"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>Back to Sign In</span>
                </button>
              </div>
            ) : (
              <form onSubmit={handleForgotPassword} className="space-y-4 pt-1">
                {resetError && (
                  <div className="p-3 bg-alert-bg border border-alert/20 rounded-card-sm flex items-start gap-2.5 text-alert text-xs">
                    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>{resetError}</span>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-ink mb-1.5">Email address</label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-ink-muted absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="email"
                      value={resetEmail}
                      onChange={(e) => setResetEmail(e.target.value)}
                      placeholder="name@example.com"
                      className="w-full pl-10 pr-4 py-3 bg-white border border-neutral-200 rounded-card text-ink text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition"
                      required
                      autoFocus
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={resetLoading}
                  className="w-full py-3.5 bg-primary hover:bg-primary-dark text-white font-semibold rounded-card shadow-sm flex items-center justify-center gap-2 transition disabled:opacity-70 text-sm"
                >
                  {resetLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span>Send Reset Link</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setShowForgotPassword(false);
                    setResetError('');
                  }}
                  className="w-full text-center text-xs text-ink-muted hover:text-ink font-medium pt-1"
                >
                  Cancel and return to sign in
                </button>
              </form>
            )}
          </div>
        ) : (
          /* Standard Sign In Form */
          <>
            {error && (
              <div className="mb-4 p-3 bg-alert-bg border border-alert/20 rounded-card-sm flex items-start gap-2.5 text-alert text-xs">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSignIn} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-ink mb-1.5">Email address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-ink-muted absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@example.com"
                    className="w-full pl-10 pr-4 py-3 bg-white border border-neutral-200 rounded-card text-ink text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition"
                    required
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="block text-xs font-semibold text-ink">Password</label>
                  <button
                    type="button"
                    onClick={() => {
                      setShowForgotPassword(true);
                      setError('');
                      setResetEmail(email || '');
                    }}
                    className="text-[11px] font-semibold text-primary hover:underline"
                  >
                    Forgot password?
                  </button>
                </div>
                <div className="relative">
                  <Lock className="w-4 h-4 text-ink-muted absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full pl-10 pr-4 py-3 bg-white border border-neutral-200 rounded-card text-ink text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition"
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading || demoLoading || googleLoading}
                className="w-full py-3.5 bg-primary hover:bg-primary-dark text-white font-semibold rounded-card shadow-sm flex items-center justify-center gap-2 transition disabled:opacity-70 text-sm mt-2"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <span>Sign in</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>

            {/* Google Sign-In */}
            <div className="relative my-4 text-center">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-neutral-200"></div>
              </div>
              <span className="relative px-3 bg-cream text-[10px] font-bold text-ink-muted uppercase tracking-wider">
                or
              </span>
            </div>

            <button
              type="button"
              onClick={handleGoogleSignIn}
              disabled={loading || demoLoading || googleLoading}
              className="w-full py-3 bg-white hover:bg-neutral-50 border border-neutral-300 text-ink font-semibold rounded-card shadow-2xs flex items-center justify-center gap-2.5 transition disabled:opacity-70 text-sm active:scale-[0.99]"
            >
              {googleLoading ? (
                <Loader2 className="w-4 h-4 animate-spin text-primary" />
              ) : (
                <>
                  <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
                  </svg>
                  <span>Continue with Google</span>
                </>
              )}
            </button>

            {/* Divider */}
            <div className="relative my-6 text-center">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-neutral-200"></div>
              </div>
              <span className="relative px-3 bg-cream text-[11px] font-semibold text-ink-muted uppercase tracking-wider">
                Fast Demo Access
              </span>
            </div>

            {/* One-Tap Demo Login Button */}
            <button
              type="button"
              onClick={handleDemoSignIn}
              disabled={loading || demoLoading || googleLoading}
              className="w-full py-3.5 bg-cream-card hover:bg-surface-tint border border-primary/20 text-ink font-semibold rounded-card shadow-xs flex items-center justify-center gap-2.5 transition disabled:opacity-70 text-sm"
            >
              {demoLoading ? (
                <Loader2 className="w-4 h-4 animate-spin text-primary" />
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4 text-primary" />
                  <span>Continue as Demo Customer</span>
                </>
              )}
            </button>

            {/* Quick Staff & Manager links */}
            <div className="mt-4 text-center space-y-2">
              <button
                type="button"
                onClick={handleStaffDemo}
                className="text-xs text-primary hover:underline font-semibold block w-full"
              >
                Switch to Exit Staff Demo (FreshMart)
              </button>
              <button
                type="button"
                onClick={handleManagerDemo}
                className="text-xs text-primary-dark hover:underline font-semibold block w-full"
              >
                Switch to Manager Dashboard Demo (FreshMart)
              </button>
              <button
                type="button"
                onClick={handleStyleHubManagerDemo}
                className="text-xs text-primary hover:underline font-semibold block w-full"
              >
                Switch to Manager Dashboard Demo (StyleHub)
              </button>
            </div>
          </>
        )}
      </div>

      {/* Footer */}
      <div className="text-center text-[11px] text-ink-muted">
        <span>SmartScan · Real Auth & Multi-Retailer</span>
      </div>
    </div>
  );
}
