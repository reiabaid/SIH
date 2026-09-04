import React, { useState } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ReportModalPreview from './components/ReportModalPreview';

import Screen00Landing from './screens/Screen00Landing';
import Screen01SelectPair from './screens/Screen01SelectPair';
import Screen02MatchReview from './screens/Screen02MatchReview';
import Screen03Evidence from './screens/Screen03Evidence';
import Screen04TerrainReport from './screens/Screen04TerrainReport';

export default function App() {
  const [currentScreen, setCurrentScreen] = useState(0); // 0: Landing, 1: Select, 2: Review, 3: Evidence, 4: Terrain
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  
  const [selectedProductA, setSelectedProductA] = useState(null);
  const [selectedProductB, setSelectedProductB] = useState(null);
  const [selectedRung, setSelectedRung] = useState('rung1');

  const handleRunDemo = () => {
    setCurrentScreen(1);
  };

  return (
    <div className="min-h-screen bg-[#0b0f17] text-slate-100 flex flex-col font-sans select-none overflow-x-hidden">
      {/* Top Mission Control Header */}
      <Header currentScreen={currentScreen} onRunDemo={handleRunDemo} />

      {/* Main Shell Viewport */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Navigation Sidebar */}
        <Sidebar currentScreen={currentScreen} setCurrentScreen={setCurrentScreen} />

        {/* Dynamic Main Workspace Content View */}
        <main className="flex-1 p-6 md:p-8 overflow-y-auto max-w-7xl mx-auto w-full">
          {currentScreen === 0 && (
            <Screen00Landing onLaunchWorkspace={() => setCurrentScreen(1)} />
          )}

          {currentScreen === 1 && (
            <Screen01SelectPair 
                onRunMatch={(productA, productB, rung) => {
                    setSelectedProductA(productA);
                    setSelectedProductB(productB);
                    setSelectedRung(rung);
                    setCurrentScreen(2);
                }} 
            />
          )}

          {currentScreen === 2 && (
            <Screen02MatchReview 
              selectedProductA={selectedProductA}
              selectedProductB={selectedProductB}
              selectedRung={selectedRung}
              onAcceptMatch={() => setCurrentScreen(3)} 
              onBack={() => setCurrentScreen(1)}
            />
          )}

          {currentScreen === 3 && (
            <Screen03Evidence onProceedToExport={() => setCurrentScreen(4)} />
          )}

          {currentScreen === 4 && (
            <Screen04TerrainReport onOpenReportModal={() => setIsReportModalOpen(true)} />
          )}
        </main>
      </div>

      {/* Live Scientific Report Preview Modal */}
      <ReportModalPreview
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
      />
    </div>
  );
}
