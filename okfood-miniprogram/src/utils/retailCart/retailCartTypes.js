/** @typedef {object} RetailCartItem
 * @property {number} retailProductId SKU id
 * @property {number} [spuId]
 * @property {string} [spuTitle]
 * @property {string} [specLabel]
 * @property {string} title
 * @property {string|null} unitPriceYuan
 * @property {string|null} listPriceYuan
 * @property {string} coverImageUrl
 * @property {number|null} stockRemaining
 * @property {boolean} stockLimited
 * @property {number} soldCount
 * @property {number} quantity
 * @property {number} addedAt
 */

/** @typedef {object} RetailCartProductInput
 * @property {number} retailProductId
 * @property {number} [spuId]
 * @property {string} [spuTitle]
 * @property {string} [specLabel]
 * @property {string} [title]
 * @property {string} [name]
 * @property {string|number|null} [unitPriceYuan]
 * @property {string|number|null} [listPriceYuan]
 * @property {string} [coverImageUrl]
 * @property {string} [img]
 * @property {string} [imgOriginal]
 * @property {number|null} [stockRemaining]
 * @property {boolean} [stockLimited]
 * @property {number} [soldCount]
 */

export {}
