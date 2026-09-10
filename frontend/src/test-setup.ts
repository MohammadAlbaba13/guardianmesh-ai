import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';
class Observer { observe(){} unobserve(){} disconnect(){} }
vi.stubGlobal('ResizeObserver',Observer);
HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};
HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};
