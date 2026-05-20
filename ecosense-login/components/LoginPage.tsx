
import React, { useState } from 'react';
import { Input } from './Input';
import { Button } from './Button';
import { Logo } from './Logo';

export const LoginPage: React.FC = () => {
  const [formData, setFormData] = useState({
    username: '',
    password: ''
  });

  // 选项 1: 森林河流 (高清)
  const imgOption1 = "https://images.unsplash.com/photo-1437482078695-73f5ca6c96e2?ixlib=rb-4.0.3&auto=format&fit=crop&w=1600&q=80";
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Logging in with:', formData);
    // Add logic to connect to auth service here
  };

  return (
    <div className="flex min-h-screen bg-white font-sans selection:bg-eco-blue selection:text-white">
      {/* Left Section: Image & Branding */}
      <div className="hidden lg:block lg:w-1/2 relative overflow-hidden">
        {/* Background Image - Nature Theme */}
        <div className="absolute inset-0">
          <img 
            src={imgOption1}
            alt="Nature landscape with river and forest" 
            className="object-cover w-full h-full"
          />
          {/* Deep Blue Overlay - Simplified and Lightened */}
          {/* 降低透明度到 20%，去除 mix-blend-multiply，让图片更透亮 */}
          <div className="absolute inset-0 bg-[#0B1727]/20"></div>
        </div>

        {/* Brand Overlay - Bigger Logo & Text */}
        <div className="absolute top-16 left-16 flex items-center gap-6 z-10">
            <div className="text-white drop-shadow-xl">
                <Logo className="w-16 h-16" /> {/* Increased from w-14 to w-16 */}
            </div>
          <span className="text-white text-4xl font-semibold tracking-wide drop-shadow-xl opacity-100">
            YueenEcoMind-AI
          </span>
        </div>
        
        {/* Quote / Tagline at bottom left */}
        <div className="absolute bottom-16 left-16 right-16 text-white z-10">
            <p className="text-2xl font-light tracking-wide opacity-100 leading-relaxed drop-shadow-md">
              Empowering a greener future through intelligence.
            </p>
            <p className="text-lg font-light opacity-90 mt-3 tracking-wider drop-shadow-md">
              通过智慧力量推动更绿色的未来
            </p>
        </div>
      </div>

      {/* Right Section: Login Form */}
      <div className="w-full lg:w-1/2 flex flex-col justify-center items-center px-8 md:px-16 xl:px-32 relative bg-white">
        
        {/* Mobile Header (Only visible on small screens) */}
        <div className="lg:hidden absolute top-8 left-8 flex items-center gap-3 mb-8">
             <div className="text-eco-blue">
                <Logo className="w-10 h-10" />
             </div>
            <span className="text-eco-blue text-2xl font-bold">YueenEcoMind-AI</span>
        </div>

        <div className="w-full max-w-[440px] space-y-12">
          
          {/* Header Text Section - STRICT Left Alignment */}
          <div className="text-left space-y-3">
            <h1 className="text-5xl text-gray-900 font-bold tracking-tight">
              Welcome Back
            </h1>
            {/* Removed 'uppercase' to preserve "YueenEcoMind-AI" casing */}
            {/* Reduced tracking slightly for better optical alignment with the H1 */}
            <p className="text-gray-400 text-sm tracking-wide font-medium">
              YueenEcoMind-AI 智慧环保中台
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-8">
            <div className="space-y-6">
              <Input
                name="username"
                type="text"
                placeholder="Username 用户名"
                value={formData.username}
                onChange={handleChange}
                required
              />
              
              <div className="space-y-2">
                <Input
                    name="password"
                    type="password"
                    placeholder="Password 密码"
                    value={formData.password}
                    onChange={handleChange}
                    required
                />
                {/* Forgot Password Link */}
                <div className="flex justify-end pt-1">
                    <a 
                        href="#" 
                        className="text-gray-400 text-xs hover:text-eco-blue transition-colors duration-300 font-medium"
                    >
                        忘记密码？
                    </a>
                </div>
              </div>
            </div>

            {/* Submit Button */}
            <div className="pt-4">
                <Button type="submit" fullWidth>
                  Login 登录
                </Button>
            </div>
          </form>

        </div>

        {/* Footer: Sign Up */}
        <div className="absolute bottom-12 w-full text-center">
            <p className="text-gray-400 text-sm">
                还没有账号？{' '}
                <a href="#" className="text-gray-800 font-semibold hover:text-eco-blue transition-colors ml-1">
                    立即注册
                </a>
            </p>
        </div>
      </div>
    </div>
  );
};
