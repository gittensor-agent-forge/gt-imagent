import type { CSSProperties, ReactNode } from "react";

type StaticEffectCardProps = {
  children: ReactNode;
  className?: string;
  radius?: number;
};

export function StaticEffectCard({ children, className = "", radius = 22 }: StaticEffectCardProps) {
  const style = { "--border-radius": `${radius}px` } as CSSProperties;

  return (
    <div className={`imagent-effect-card imagent-effect-card--static ${className}`} style={style}>
      <div className="border-glow-inner">
        <div className="imagent-effect-card__glare">
          <div className="imagent-effect-card__content">{children}</div>
        </div>
      </div>
    </div>
  );
}
