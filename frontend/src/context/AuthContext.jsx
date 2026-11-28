import React, { createContext, useContext, useState, useEffect } from 'react';
import { supabase } from '../services/supabase';
import { api } from '../services/api';

const AuthContext = createContext(null);

export const DEMO_PASSWORD = 'SmartScanDemo2026!';

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  // Load user profile from server-side FastAPI endpoint (immune to client RLS issues)
  const loadProfile = async (currentUser) => {
    if (!currentUser) {
      setProfile(null);
      return;
    }
    try {
      // First try /auth/bootstrap to ensure profile is provisioned in app2026.profiles
      const data = await api.bootstrap();
      setProfile({
        id: data.id,
        role: data.role || 'customer',
        store_id: data.store_id,
        display_name: data.display_name || currentUser.user_metadata?.full_name || currentUser.email?.split('@')[0] || 'Customer',
        store: data.store || null,
      });
    } catch (err) {
      console.warn('Failed to load profile via backend bootstrap, falling back to getMe:', err);
      try {
        const data = await api.getMe();
        setProfile({
          id: data.id,
          role: data.role || 'customer',
          store_id: data.store_id,
          display_name: data.display_name || currentUser.user_metadata?.full_name || currentUser.email?.split('@')[0] || 'Customer',
          store: data.store || null,
        });
      } catch (err2) {
        setProfile({
          id: currentUser.id,
          role: 'customer',
          store_id: null,
          display_name: currentUser.user_metadata?.full_name || currentUser.user_metadata?.name || currentUser.email?.split('@')[0] || 'Customer',
        });
      }
    }
  };

  useEffect(() => {
    let mounted = true;

    // Check active session on initial load
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!mounted) return;
      setSession(session);
      setUser(session?.user ?? null);
      if (session?.user) {
        loadProfile(session.user).finally(() => {
          if (mounted) setLoading(false);
        });
      } else {
        setLoading(false);
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (_event, session) => {
      if (!mounted) return;
      setSession(session);
      setUser(session?.user ?? null);
      if (session?.user) {
        await loadProfile(session.user);
      } else {
        setProfile(null);
      }
      setLoading(false);
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const signIn = async (email, password) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    return data;
  };

  const signInDemo = async () => {
    return signIn('demo@smartscan.app', DEMO_PASSWORD);
  };

  const signInStaffDemo = async () => {
    return signIn('staff@smartscan.app', DEMO_PASSWORD);
  };

  const signInManagerDemo = async () => {
    return signIn('manager@smartscan.app', DEMO_PASSWORD);
  };

  const signInStyleHubManagerDemo = async () => {
    return signIn('manager-sh@smartscan.app', DEMO_PASSWORD);
  };

  const signInWithGoogle = async () => {
    const redirectTo = window.location.origin + '/';
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo,
      },
    });
    if (error) throw error;
    return data;
  };

  const resetPasswordForEmail = async (email) => {
    const redirectTo = window.location.origin + '/?screen=reset-password';
    const { data, error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo,
    });
    if (error) throw error;
    return data;
  };

  const updateUserPassword = async (password) => {
    const { data, error } = await supabase.auth.updateUser({ password });
    if (error) throw error;
    return data;
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    setSession(null);
    setUser(null);
    setProfile(null);
  };

  return (
    <AuthContext.Provider
      value={{
        session,
        user,
        profile,
        loading,
        signIn,
        signInWithGoogle,
        resetPasswordForEmail,
        updateUserPassword,
        signInDemo,
        signInStaffDemo,
        signInManagerDemo,
        signInStyleHubManagerDemo,
        signOut,
        refreshProfile: () => user && loadProfile(user),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
