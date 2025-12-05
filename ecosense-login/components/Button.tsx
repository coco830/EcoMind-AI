import React from 'react';
import { ButtonProps } from '../types';

export const Button: React.FC<ButtonProps> = ({ 
  children, 
  variant = 'primary', 
  fullWidth = false, 
  className = '', 
  ...props 
}) => {
  
  const baseStyles = "py-4 px-6 rounded-full font-medium tracking-wide transition-all duration-300";
  
  const variants = {
    // Deep Gray-Blue (#0B1727) to match the overlay.
    // Matte finish: No high-gloss gradients, just subtle depth.
    // Soft Shadow: shadow-blue-900/20 is a colored shadow for a premium feel.
    primary: `
      bg-[#0B1727] text-white 
      shadow-[0_8px_20px_rgba(11,23,39,0.25)] 
      hover:shadow-[0_12px_28px_rgba(11,23,39,0.35)] 
      hover:-translate-y-0.5
      active:translate-y-0 active:shadow-[0_4px_10px_rgba(11,23,39,0.2)]
    `,
    outline: "border-2 border-eco-blue text-eco-blue hover:bg-blue-50",
    ghost: "text-eco-blue hover:bg-blue-50"
  };

  return (
    <button
      className={`
        ${baseStyles}
        ${variants[variant]}
        ${fullWidth ? 'w-full' : ''}
        ${className}
      `}
      {...props}
    >
      {children}
    </button>
  );
};