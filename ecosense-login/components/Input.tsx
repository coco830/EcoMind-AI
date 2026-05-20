import React from 'react';
import { InputProps } from '../types';

export const Input: React.FC<InputProps> = ({ className = '', ...props }) => {
  return (
    <input
      className={`
        w-full px-6 py-4
        bg-[#F7F8FA] border-none
        rounded-2xl text-gray-800 placeholder-gray-400
        shadow-[inset_0_1px_2px_rgba(0,0,0,0.03)]
        focus:outline-none focus:bg-white focus:ring-0 
        focus:shadow-[0_10px_30px_rgba(0,0,0,0.08),inset_0_0_0_1.5px_#E5E7EB]
        hover:bg-[#F0F2F5]
        transition-all duration-300 ease-out
        text-base
        ${className}
      `}
      {...props}
    />
  );
};