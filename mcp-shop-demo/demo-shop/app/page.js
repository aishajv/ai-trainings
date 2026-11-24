'use client';

import { useState } from 'react';

const PRICE = 89;

export default function Shop() {
  const [qty, setQty] = useState(1);
  const [code, setCode] = useState('');
  const [applied, setApplied] = useState(false);
  const [invalid, setInvalid] = useState(false);
  const [showCookies, setShowCookies] = useState(true);

  const subtotal = PRICE * qty;
  const discount = applied ? subtotal * 0.1 : 0;
  let total = subtotal - discount;
  if (applied) total = total * 0.9;

  const eur = (n) => '€' + n.toFixed(2);

  function applyCoupon() {
    const ok = code.trim().toUpperCase() === 'SAVE10';
    setApplied(ok);
    setInvalid(!ok);
  }

  return (
    <>
      <header className="header">
        <a className="logo" href="#">Demo Shop</a>
        <nav className="nav">
          <a href="#">Shop</a>
          <a href="#">About</a>
          <a href="#">Cart (1)</a>
        </nav>
      </header>

      <main className="main">
        <section className="card product">
          <div className="product-image">
            <svg width="160" height="200" viewBox="0 0 160 200" fill="none" stroke="#2f5bea" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M40 180 H120" />
              <path d="M80 180 V150" />
              <path d="M80 150 L50 90" />
              <path d="M50 90 L105 45" />
              <path d="M92 30 L128 72 L100 82 L82 40 Z" />
              <path d="M108 92 L114 104" />
            </svg>
          </div>
          <div className="details">
            <span className="eyebrow">Lighting</span>
            <h1 className="title">Halo Pro Adjustable LED Desk Lamp with Wireless Charging Base</h1>
            <div className="price-row">
              <span className="price">€89.00</span>
              <span className="badge">In stock</span>
            </div>
            <p className="desc">Warm to cool light in five steps, a base that charges your phone, and an arm that stays where you put it.</p>
            <div className="field">
              <span className="label">Quantity</span>
              <div className="qty">
                <button aria-label="Decrease quantity" onClick={() => setQty(Math.max(1, qty - 1))}>−</button>
                <span>{qty}</span>
                <button aria-label="Increase quantity" onClick={() => setQty(Math.min(9, qty + 1))}>+</button>
              </div>
            </div>
          </div>
        </section>

        <section className="card checkout">
          <h2>Checkout</h2>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" placeholder="you@example.com" />
          </div>
          <div className="field">
            <label htmlFor="coupon">Coupon code</label>
            <div className="coupon">
              <input id="coupon" placeholder="SAVE10" value={code} onChange={(e) => { setCode(e.target.value); setInvalid(false); }} />
              <button onClick={applyCoupon}>Apply</button>
            </div>
            {applied && <span className="ok">SAVE10 applied: 10% off</span>}
            {invalid && <span className="err">That code doesn&apos;t work</span>}
          </div>
          <div className="summary">
            <div className="row"><span>Subtotal</span><span>{eur(subtotal)}</span></div>
            <div className="row"><span>Discount</span><span>{applied ? '−' + eur(discount) : eur(0)}</span></div>
            <div className="row"><span>Shipping</span><span>Free</span></div>
            <div className="row total"><span>Total</span><span data-testid="total">{eur(total)}</span></div>
          </div>
          <button className="place-order">Place order</button>
          <span className="small">Free returns within 30 days.</span>
        </section>
      </main>

      {showCookies && (
        <div className="cookie">
          <span>We use cookies to keep your cart between visits. By continuing you agree to our cookie policy.</span>
          <button onClick={() => setShowCookies(false)}>Accept</button>
        </div>
      )}
    </>
  );
}
