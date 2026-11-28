import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { supabase } from '../services/supabase';
import { Lock, ArrowRight, CheckCircle2, AlertCircle, Loader2, ArrowLeft } from 'lucide-react';

export default function ResetPasswordScreen({ onNavigate }) {
  const { updateUserPassword, signOut } = useAuth();
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [checkingLink, setCheckingLink] = useState(true);
  const [isRecoveryValid, setIsRecoveryValid] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    let mounted = true;

    // Check URL hash for error or recovery type
    const hash = typeof window !== 'undefined' ? window.location.hash : '';
    const params = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : new URLSearchParams();

    // If Supabase returned an error in the hash (e.g. #error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired)
    if (hash.includes('error=') || hash.includes('error_code=')) {
      if (mounted) {
        setIsRecoveryValid(false);
        setError('This password reset link is invalid or has expired. Please request a new link.');
        setCheckingLink(false);
      }
      return;
    }

    // Check if recovery session is active
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!mounted) return;
      if (session || hash.includes('type=recovery') || hash.includes('access_token=')) {
        setIsRecoveryValid(true);
      } else {
        setIsRecoveryValid(false);
        setError('No active password reset session found. Please request a password reset link.');
      }
      setCheckingLink(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (!mounted) return;
      if (event === 'PASSWORD_RECOVERY' || (session && hash.includes('type=recovery'))) {
        setIsRecoveryValid(true);
        setError('');
      }
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setError('');

    if (newPassword.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }

    setLoading(true);
    try {
      await updateUserPassword(newPassword);
      setSuccess(true);
    } catch (err) {
      setError(err.message || 'Failed to update password. Link may have expired.');
    } finally {
      setLoading(false);
    }
  };

  const handleReturnToLogin = async () => {
    try {
      await signOut();
    } catch (e) {
      // Ignore
    }
    if (typeof window !== 'undefined') {
      window.location.href = '/';
    } else if (onNavigate) {
      onNavigate('home');
    }
  };

  if (checkingLink) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-cream px-6 py-12 text-center space-y-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-xs font-semibold text-ink-muted">Verifying recovery link...</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col justify-between px-6 py-8 overflow-y-auto bg-cream">
      {/* Brand & Header */}
      <div className="flex flex-col items-center text-center mt-3">
        <div className="w-14 h-14 bg-primary rounded-2xl flex items-center justify-center shadow-md mb-2.5 p-2.5">
          <svg viewBox="0 0 48 48" fill="none" className="w-9 h-9 text-cream" xmlns="http://www.w3.org/2000/svg">
            <path d="M14 16V12C14 6.47715 18.4772 2 24 2C29.5228 2 34 6.47715 34 12V16" stroke="#F6F2E7" strokeWidth="4" strokeLinecap="round"/>
            <rect x="6" y="14" width="36" height="30" rx="6" fill="#14532D" stroke="#F6F2E7" strokeWidth="3"/>
            <path d="M16 29L22 35L33 21" stroke="#F6F2E7" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <h1 className="text-xl font-bold text-ink tracking-tight">SmartScan</h1>
        <p className="text-ink-muted text-xs font-medium">Create New Password</p>
      </div>

      {/* Main Content Card */}
      <div className="w-full max-w-sm mx-auto my-6">
        {success ? (
          <div className="bg-white rounded-card p-6 border border-surface-tint shadow-xs text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="font-bold text-sm text-ink">Password updated - login now</h3>
              <p className="text-xs text-ink-muted leading-relaxed">
                Your password has been successfully reset. You can now sign in with your new credentials.
              </p>
            </div>
            <button
              type="button"
              onClick={handleReturnToLogin}
              className="w-full py-3.5 bg-primary hover:bg-primary-dark text-white font-semibold rounded-card shadow-sm flex items-center justify-center gap-2 transition text-xs"
            >
              <span>Go to Sign In</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        ) : !isRecoveryValid ? (
          <div className="bg-white rounded-card p-6 border border-alert/20 shadow-xs text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-alert-bg text-alert flex items-center justify-center mx-auto">
              <AlertCircle className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="font-bold text-sm text-ink">Invalid or Expired Link</h3>
              <p className="text-xs text-ink-muted leading-relaxed">
                {error || 'This password reset link is invalid or has expired. Please request a new link from the sign-in screen.'}
              </p>
            </div>
            <button
              type="button"
              onClick={handleReturnToLogin}
              className="w-full py-3.5 bg-primary hover:bg-primary-dark text-white font-semibold rounded-card shadow-sm flex items-center justify-center gap-2 transition text-xs"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Sign In</span>
            </button>
          </div>
        ) : (
          <div className="bg-white rounded-card p-6 border border-surface-tint shadow-xs space-y-4">
            <div className="space-y-1">
              <h3 className="font-bold text-sm text-ink">Set New Password</h3>
              <p className="text-xs text-ink-muted leading-relaxed">
                Choose a strong password with at least 6 characters.
              </p>
            </div>

            {error && (
              <div className="p-3 bg-alert-bg border border-alert/20 rounded-card-sm flex items-start gap-2.5 text-alert text-xs">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleResetPassword} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-ink mb-1.5">New Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-ink-muted absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="At least 6 characters"
                    className="w-full pl-10 pr-4 py-3 bg-white border border-neutral-200 rounded-card text-ink text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition"
                    required
                    minLength={6}
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-ink mb-1.5">Confirm Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-ink-muted absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter new password"
                    className="w-full pl-10 pr-4 py-3 bg-white border border-neutral-200 rounded-card text-ink text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition"
                    required
                    minLength={6}
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 bg-primary hover:bg-primary-dark text-white font-semibold rounded-card shadow-sm flex items-center justify-center gap-2 transition disabled:opacity-70 text-sm mt-2"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <span>Update Password</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={handleReturnToLogin}
                className="w-full text-center text-xs text-ink-muted hover:text-ink font-medium pt-1"
              >
                Cancel and return to sign in
              </button>
            </form>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="text-center text-[11px] text-ink-muted">
        <span>SmartScan · Secure Auth Recovery</span>
      </div>
    </div>
  );
}
