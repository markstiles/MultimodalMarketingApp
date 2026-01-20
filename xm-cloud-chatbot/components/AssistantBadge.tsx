'use client';

import { AssistantType } from '@/lib/types/assistant';
import { ASSISTANT_TEMPLATES } from '@/lib/prompts/templates';

interface AssistantBadgeProps {
  type: AssistantType;
}

export default function AssistantBadge({ type }: AssistantBadgeProps) {
  const config = ASSISTANT_TEMPLATES[type];

  const colorClasses = {
    blue: 'bg-blue-100 text-blue-800 border-blue-200',
    purple: 'bg-purple-100 text-purple-800 border-purple-200',
    green: 'bg-green-100 text-green-800 border-green-200',
    orange: 'bg-orange-100 text-orange-800 border-orange-200',
    teal: 'bg-teal-100 text-teal-800 border-teal-200',
  };

  return (
    <div
      className={`inline-flex items-center space-x-2 px-3 py-1.5 rounded-full border transition-all ${
        colorClasses[config.color as keyof typeof colorClasses]
      }`}
    >
      <span className="text-lg">{config.icon}</span>
      <span className="text-sm font-medium">{config.name}</span>
    </div>
  );
}
