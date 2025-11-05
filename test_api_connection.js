#!/usr/bin/env node

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

console.log('🧪 Testing API Connection');
console.log('==========================');
console.log(`Backend URL: ${API_BASE_URL}`);

async function testConnection() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    console.log(`✅ Response Status: ${response.status}`);
    
    if (response.ok) {
      const data = await response.json();
      console.log('✅ Health Check Success:');
      console.log(`   - Status: ${data.status}`);
      console.log(`   - Excel Converter: ${data.services.excel_converter}`);
      console.log(`   - ICE Ingestion: ${data.services.ice_ingestion}`);
      console.log('🎉 API CONNECTION WORKING!');
    } else {
      const errorText = await response.text();
      console.log(`❌ Error Response: ${errorText}`);
    }
  } catch (error) {
    console.log(`❌ Connection Failed: ${error.message}`);
    console.log('   Possible causes:');
    console.log('   - Backend not running on port 8000');
    console.log('   - CORS configuration issue'); 
    console.log('   - Network connectivity problem');
  }
}

testConnection();