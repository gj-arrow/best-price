import React from 'react';
import styles from './PriceBlock.module.css';

export interface PriceBlockProps {
  /** Minimum price value */
  min: number;
  /** Maximum price value */
  max: number;
  /** Total/average price value */
  total: number;
  /** Currency symbol */
  currency?: string;
  /** Custom label for min */
  minLabel?: string;
  /** Custom label for max */
  maxLabel?: string;
  /** Custom label for total */
  totalLabel?: string;
  /** Title for the price block */
  title?: string;
  /** Additional CSS class */
  className?: string;
  /** Whether to show compact mode */
  compact?: boolean;
}

/**
 * PriceBlock - Statistics display component for price information
 * 
 * Displays min, max, and total price statistics in a structured format.
 * Supports compact mode for space-constrained layouts.
 */
export const PriceBlock: React.FC<PriceBlockProps> = ({
  min,
  max,
  total,
  currency = '$',
  minLabel = 'Min',
  maxLabel = 'Max',
  totalLabel = 'Total',
  title,
  className = '',
  compact = false,
}) => {
  const formatPrice = (value: number): string => {
    return `${currency}${value.toFixed(2)}`;
  };

  const range = max - min;
  const rangePercent = min > 0 ? ((range / min) * 100).toFixed(0) : 0;

  return (
    <div className={`${styles.priceBlock} ${compact ? styles.compact : ''} ${className}`}>
      {title && (
        <h4 className={styles.title}>{title}</h4>
      )}

      <div className={styles.stats}>
        <div className={styles.stat}>
          <span className={styles.statLabel}>{minLabel}</span>
          <span className={`${styles.statValue} ${styles.min}`}>
            {formatPrice(min)}
          </span>
        </div>

        <div className={styles.stat}>
          <span className={styles.statLabel}>{maxLabel}</span>
          <span className={`${styles.statValue} ${styles.max}`}>
            {formatPrice(max)}
          </span>
        </div>

        <div className={styles.stat}>
          <span className={styles.statLabel}>{totalLabel}</span>
          <span className={`${styles.statValue} ${styles.total}`}>
            {formatPrice(total)}
          </span>
        </div>
      </div>

      {!compact && (
        <div className={styles.range}>
          <span className={styles.rangeLabel}>Range:</span>
          <span className={styles.rangeValue}>
            {formatPrice(range)} ({rangePercent}%)
          </span>
        </div>
      )}
    </div>
  );
};

export default PriceBlock;
