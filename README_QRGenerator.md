# QR Code Generator

A modern, responsive QR code generator built with Next.js, TypeScript, and TailwindCSS.

## Features

- ✅ **Instant QR Code Generation**: Generate QR codes from any URL or text in real-time
- ✅ **Modern UI**: Clean, responsive design with TailwindCSS
- ✅ **Download Support**: Download generated QR codes as PNG images
- ✅ **Real-time Preview**: See QR code updates as you type
- ✅ **TypeScript**: Full type safety throughout the application
- ✅ **Optimized**: Next.js 15 with App Router for best performance

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: TailwindCSS v3
- **QR Generation**: qrcode library
- **Build Tool**: Turbopack

## Project Structure

```
qr-generator/
├── app/
│   ├── components/
│   │   └── QRGenerator.tsx    # Main QR generator component
│   ├── lib/                   # Utility libraries (if needed)
│   ├── globals.css            # Global styles with TailwindCSS
│   ├── layout.tsx             # Root layout component
│   └── page.tsx               # Home page
├── postcss.config.mjs         # PostCSS configuration
├── tailwind.config.js         # TailwindCSS configuration
└── tsconfig.json              # TypeScript configuration
```

## Configuration Details

### Key Configuration Directives (Following Best Practices):

1. **TailwindCSS v3 Stable**: Using stable version for production reliability
2. **PostCSS Setup**: Configured with `tailwindcss` and `autoprefixer`
3. **Co-located Architecture**: Components and utilities inside `/app` directory
4. **Path Aliases**: `@/*` alias configured for clean imports
5. **CSS Import**: `globals.css` imported only in `app/layout.tsx`

## Getting Started

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Start development server**:
   ```bash
   npm run dev
   ```

3. **Build for production**:
   ```bash
   npm run build
   ```

4. **Start production server**:
   ```bash
   npm start
   ```

## Usage

1. Open the application in your browser
2. Enter any URL or text in the input field
3. The QR code will be generated automatically as you type
4. Click "Download QR Code" to save the image

## Features in Detail

### QR Code Generation
- Uses the `qrcode` library for high-quality QR code generation
- Configurable size (256x256 pixels)
- Black and white color scheme for maximum compatibility
- Error correction level automatically optimized

### User Experience
- **Real-time Generation**: QR codes update as you type (with 300ms debounce)
- **Loading States**: Shows spinner while generating
- **Error Handling**: Graceful error messages for invalid inputs
- **Responsive Design**: Works on desktop, tablet, and mobile devices

### Performance
- **Static Generation**: Pages are pre-rendered for faster loading
- **Optimized Images**: Uses Next.js Image component for better performance
- **Code Splitting**: Automatic code splitting for smaller bundles

## Development

### File Organization
- All components are in `app/components/`
- Use the `@/` alias for imports: `import Component from '@/app/components/Component'`
- TailwindCSS classes are used for all styling

### Best Practices Implemented
- TypeScript for type safety
- ESLint for code quality
- Responsive design patterns
- Accessibility features (proper labels, alt text)
- SEO optimizations (meta tags, semantic HTML)

## License

This project is open source and available under the MIT License.