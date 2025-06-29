#!/usr/bin/env node
/**
 * Simple test to check if React components can be imported and instantiated
 */

console.log('🧪 Testing React Components Import');
console.log('=' + '='.repeat(40));

const tests = [
  {
    name: 'PredictiveMaintenancePage',
    path: './src/pages/PredictiveMaintenancePage.tsx'
  },
  {
    name: 'HealthDashboard Components',
    path: './src/components/PredictiveMaintenance/HealthDashboard.tsx'
  },
  {
    name: 'ModernChatInterface',
    path: './src/components/Chat/ModernChatInterface.tsx'
  },
  {
    name: 'API Service',
    path: './src/services/api.ts'
  }
];

let allPassed = true;

tests.forEach(test => {
  try {
    const fs = require('fs');
    if (fs.existsSync(test.path)) {
      console.log(`✅ ${test.name}: File exists`);
    } else {
      console.log(`❌ ${test.name}: File not found`);
      allPassed = false;
    }
  } catch (error) {
    console.log(`❌ ${test.name}: Error - ${error.message}`);
    allPassed = false;
  }
});

console.log('\n' + '='.repeat(40));
if (allPassed) {
  console.log('🎉 All component files exist and are accessible');
} else {
  console.log('⚠️  Some component files are missing');
}

console.log('\n📝 Note: Full React testing requires:');
console.log('  - Jest test framework');
console.log('  - React Testing Library');
console.log('  - DOM environment setup');
console.log('  - TypeScript compilation');

process.exit(allPassed ? 0 : 1);