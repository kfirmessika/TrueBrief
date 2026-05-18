'use client';

import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import type { HTMLMotionProps } from 'framer-motion';

// ---------------------------------------------------------------------------
// FadeIn — generic fade + lift entrance for any element
// ---------------------------------------------------------------------------
interface FadeInProps extends HTMLMotionProps<'div'> {
  delay?: number;
  duration?: number;
  y?: number;
}

export function FadeIn({ delay = 0, duration = 0.2, y = 8, children, ...props }: FadeInProps) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: reduced ? 0 : y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduced ? 0 : duration, delay, ease: [0.4, 0, 0.2, 1] }}
      {...props}
    >
      {children}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// StaggerList — parent that staggers children via AnimatePresence + variants
// ---------------------------------------------------------------------------
interface StaggerListProps {
  children: React.ReactNode;
  className?: string;
  stagger?: number;
}

const listVariants = {
  hidden: {},
  visible: (stagger: number) => ({
    transition: { staggerChildren: stagger },
  }),
};

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { ease: [0.4, 0, 0.2, 1] as [number, number, number, number], duration: 0.2 },
  },
};

export function StaggerList({ children, className, stagger = 0.06 }: StaggerListProps) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      variants={listVariants}
      initial="hidden"
      animate="visible"
      custom={stagger}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <motion.div className={className} variants={itemVariants}>
      {children}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// PageTransition — wraps page content; animates on route change
// Usage: wrap each page's root <div> in <PageTransition>
// ---------------------------------------------------------------------------
export function PageTransition({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <AnimatePresence mode="wait">
      <motion.div
        className={className}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

// ---------------------------------------------------------------------------
// ScalePop — button / card press animation
// ---------------------------------------------------------------------------
export function ScalePop({ children, className, ...props }: HTMLMotionProps<'div'> & { className?: string }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      whileHover={reduced ? {} : { scale: 1.02 }}
      whileTap={reduced ? {} : { scale: 0.97 }}
      transition={{ duration: 0.12, ease: [0.34, 1.56, 0.64, 1] }}
      {...props}
    >
      {children}
    </motion.div>
  );
}
