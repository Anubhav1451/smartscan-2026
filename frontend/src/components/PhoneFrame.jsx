import React from 'react';
import { useAuth } from '../context/AuthContext';

export default function PhoneFrame({ children, currentScreen, onNavigate }) {
  const { user, profile } = useAuth();
  const isStaff = profile?.role === 'exit_staff';
  const isManager = profile?.role === 'manager';

  return (
    <div className="h-screen w-full bg-cream sm:px-3 sm:pt-2 flex flex-col font-sans antialiased">
      {/* Top Quick Switcher Bar for reviewers */}
      <div className="w-full mb-2 hidden sm:flex items-center justify-between text-xs bg-white rounded-full p-1 border border-primary/15 shadow-sm shrink-0">
        {!user ? (
          <span className="w-full text-center py-1 font-semibold text-ink/70">
            SmartScan · Phase 2 Live Prototype (Sign in below)
          </span>
        ) : isStaff ? (
          <span className="w-full text-center py-1 font-semibold text-ink/70">
            Exit Staff Mode · {profile?.store?.name || 'FreshMart'}
          </span>
        ) : isManager ? (
          <span className="w-full text-center py-1 font-semibold text-ink/70">
            Manager Mode · {profile?.store?.name || 'FreshMart'}
          </span>
        ) : (
          <>
            <button
              type="button"
              onClick={() => onNavigate('home')}
              className={`flex-1 py-1 rounded-full font-semibold transition-all ${
                currentScreen === 'home' 
                  ? 'bg-primary text-white shadow-xs' 
                  : 'text-ink/60 hover:text-ink'
              }`}
            >
              Home
            </button>
            <button
              type="button"
              onClick={() => onNavigate('store')}
              className={`flex-1 py-1 rounded-full font-semibold transition-all ${
                currentScreen === 'store' 
                  ? 'bg-primary text-white shadow-xs' 
                  : 'text-ink/60 hover:text-ink'
              }`}
            >
              Store
            </button>
            <button
              type="button"
              onClick={() => onNavigate('scanner')}
              className={`flex-1 py-1 rounded-full font-semibold transition-all ${
                currentScreen === 'scanner' 
                  ? 'bg-primary text-white shadow-xs' 
                  : 'text-ink/60 hover:text-ink'
              }`}
            >
              Scan
            </button>
            <button
              type="button"
              onClick={() => onNavigate('cart')}
              className={`flex-1 py-1 rounded-full font-semibold transition-all ${
                currentScreen === 'cart' 
                  ? 'bg-primary text-white shadow-xs' 
                  : 'text-ink/60 hover:text-ink'
              }`}
            >
              Cart
            </button>
            <button
              type="button"
              onClick={() => onNavigate('orders')}
              className={`flex-1 py-1 rounded-full font-semibold transition-all ${
                currentScreen === 'orders' 
                  ? 'bg-primary text-white shadow-xs' 
                  : 'text-ink/60 hover:text-ink'
              }`}
            >
              Orders
            </button>
          </>
        )}
      </div>

      {/* Full-screen app viewport */}
      <div className="flex-1 w-full bg-cream flex flex-col overflow-hidden relative">

        {/* Screen View Container */}
        <div className="flex-1 overflow-hidden relative flex flex-col">
          {children}
        </div>
      </div>
      
    </div>
  );
}
