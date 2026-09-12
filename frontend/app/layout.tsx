import type { Metadata } from 'next';
import './globals.css';
import { AppContextProvider } from './context/AppContext';
import { NavSidebar } from '@/components/NavSidebar';
import { GlobalModals } from '@/components/GlobalModals';

export const metadata: Metadata = {
  title: 'CivicLens | Civic Intelligence Command Center',
  description: 'AI-powered multi-agent platform for municipal policy analysis, legal verification & citizen impact reporting.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased" style={{ background: 'var(--bg-base)', color: 'var(--text-primary)' }}>
        <AppContextProvider>
          <div className="flex min-h-screen">
            {/* Sidebar */}
            <NavSidebar />

            {/* Main content — offset by nav width */}
            <main
              className="flex-1 min-h-screen overflow-y-auto"
              style={{ marginLeft: 'var(--nav-width)' }}
            >
              {children}
            </main>
          </div>

          {/* Global modals — rendered at root so any page can trigger them */}
          <GlobalModals />
        </AppContextProvider>
      </body>
    </html>
  );
}
