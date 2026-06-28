interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  className?: string;
  variant?: 'text' | 'circular' | 'rectangular';
}

export function Skeleton({
  width,
  height,
  borderRadius = '4px',
  className = '',
  variant,
}: SkeletonProps) {
  const variantStyles = {
    text: { height: '12px', borderRadius: '3px' },
    circular: { borderRadius: '9999px' },
    rectangular: { borderRadius: '4px' },
  };

  const finalBorderRadius = variant ? variantStyles[variant]?.borderRadius ?? borderRadius : borderRadius;
  const finalHeight = variant === 'text' ? variantStyles.text.height : height;

  return (
    <div
      className={`bg-white/[0.06] animate-pulse ${className}`}
      style={{
        width: width ?? '100%',
        height: finalHeight ?? '12px',
        borderRadius: finalBorderRadius,
      }}
    />
  );
}

export function ProductCardSkeleton() {
  return (
    <div className="flex flex-col gap-2 p-3">
      <Skeleton height="120px" />
      <Skeleton variant="text" className="w-3/4" />
      <Skeleton variant="text" className="w-1/3" />
      <Skeleton height="28px" />
    </div>
  );
}

export default Skeleton;
