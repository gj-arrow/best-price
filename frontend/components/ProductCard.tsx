import React from 'react';
import styles from './ProductCard.module.css';

export interface ProductCardProps {
  name: string;
  description?: string;
  imageUrl?: string;
  price: number;
  originalPrice?: number;
  currency?: string;
  isBestPrice?: boolean;
  bestPriceLabel?: string;
  storeName?: string;
  storeUrl?: string;
  className?: string;
}

export const ProductCard: React.FC<ProductCardProps> = ({
  name,
  description,
  imageUrl,
  price,
  originalPrice,
  currency = '$',
  isBestPrice = false,
  bestPriceLabel = 'Лучшая цена',
  storeName = 'Магазин',
  storeUrl = '#',
  className = '',
}) => {
  const formatPrice = (value: number): string => {
    const fixed = value.toFixed(1);
    // если целое — без десятых, иначе с одной десятой
    return Number.isInteger(value) ? String(Math.round(value)) : fixed;
  };

  const hasDiscount = originalPrice !== undefined && originalPrice > price;
  const discountPercent = hasDiscount
    ? Math.round(((originalPrice - price) / originalPrice) * 100)
    : 0;

  return (
    <div className={`${styles.card} ${isBestPrice ? styles.bestPrice : ''} ${className}`}>
      {isBestPrice && (
        <div className={styles.badge}>{bestPriceLabel}</div>
      )}

      {imageUrl && (
        <div className={styles.imageWrapper}>
          <img src={imageUrl} alt={name} className={styles.image} loading="lazy" />
        </div>
      )}

      <div className={styles.content}>
        <h3 className={styles.name}>{name}</h3>
        {description && <p className={styles.description}>{description}</p>}

        <div className={styles.priceRow}>
          <div className={styles.priceWrapper}>
            <span className={styles.price}>{currency === 'BYN' || currency === '₽' || currency === 'р.' ? `${formatPrice(price)} ${currency}` : `${currency}${formatPrice(price)}`}</span>
            {hasDiscount && (
              <span className={styles.originalPrice}>{currency === 'BYN' || currency === '₽' || currency === 'р.' ? `${formatPrice(originalPrice!)} ${currency}` : `${currency}${formatPrice(originalPrice!)}`}</span>
            )}
          </div>
          {hasDiscount && (
            <span className={styles.discount}>-{discountPercent}%</span>
          )}
        </div>

        <div className={styles.storeRow}>
          <span className={styles.storeName}>{storeName}</span>
        </div>

        <a
          href={storeUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.buyButton}
        >
          <svg className={styles.buyIcon} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
          </svg>
          Перейти на сайт
        </a>
      </div>
    </div>
  );
};

export default ProductCard;
