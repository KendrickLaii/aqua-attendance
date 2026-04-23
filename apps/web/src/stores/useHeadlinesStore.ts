import type { HeadlinesProperties, Content } from '@/types/headlines'
import type { HeadlinesFormData } from '@/components/dialogs/tax/HeadlinesDialog.vue'
import { getAllHeadlines, createHeadlines, updateHeadlines, deleteHeadlines } from '@/api/headlines'

/**
 * Headlines Store
 * 
 * Centralized state management for headlines data using Pinia.
 * This store handles all headlines-related operations including:
 * - Fetching and caching headlines data
 * - CRUD operations (Create, Read, Update, Delete)
 * - Search and filtering
 * - Pagination and sorting
 * - Loading and error states
 * 
 * Benefits:
 * - Single source of truth for headlines data across the application
 * - Reusable business logic for all components
 * - Automatic reactivity when data changes
 * - Persistent state across component navigation
 */
export const useHeadlinesStore = defineStore('headlines', {
  /**
   * State
   * 
   * Defines the reactive data structure for the store.
   * All properties are reactive and can be accessed/modified by components.
   */
  state: () => ({
    // Core data
    headlines: [] as Content[],              // Array of all headlines fetched from the server
    totalCount: 0,                           // Total number of headlines (from server response)
    
    // UI states
    loading: false,                          // Loading indicator for async operations
    error: null as string | null,            // Error message if any operation fails
    
    // Search and filter
    searchQuery: '',                         // Current search query string
    
    // Pagination
    page: 1,                                 // Current page number (1-indexed)
    itemsPerPage: 10,                        // Number of items to display per page
    
    // Sorting
    sortBy: undefined as string | undefined, // Field to sort by (e.g., 'title', 'updated_at')
    orderBy: undefined as string | undefined,// Sort order ('asc' or 'desc')
    
    // Selection
    selectedRows: [] as Content[],           // Currently selected rows in the data table

    // Loaded
    loaded: false,                           // Whether the headlines data has been loaded
  }),

  /**
   * Getters
   * 
   * Computed properties that derive state from the store.
   * These are cached and only recompute when their dependencies change.
   * Think of them as computed properties in Vue components.
   */
  getters: {
    /**
     * Returns headlines filtered by the search query.
     * Searches across title, index_type, remark, and status fields.
     * 
     * @returns {Content[]} Filtered array of headlines
     */
    filteredHeadlines: (state) => {
      if (!state.searchQuery) return state.headlines

      const query = state.searchQuery.toLowerCase()
      return state.headlines.filter(headline => 
        headline.title?.toLowerCase().includes(query) ||
        headline.index_type?.toLowerCase().includes(query) ||
        headline.remark?.toLowerCase().includes(query) ||
        headline.status?.toLowerCase().includes(query)
      )
    },

    /**
     * Returns paginated headlines based on current page and items per page.
     * Applies search filter first, then slices the array for pagination.
     * 
     * Note: Currently not used in the component, but available for future use.
     * 
     * @returns {Content[]} Paginated array of headlines
     */
    paginatedHeadlines: (state) => {
      const filtered = state.searchQuery ? 
        state.headlines.filter(headline => 
          headline.title?.toLowerCase().includes(state.searchQuery.toLowerCase()) ||
          headline.index_type?.toLowerCase().includes(state.searchQuery.toLowerCase()) ||
          headline.remark?.toLowerCase().includes(state.searchQuery.toLowerCase()) ||
          headline.status?.toLowerCase().includes(state.searchQuery.toLowerCase())
        ) : state.headlines

      const start = (state.page - 1) * state.itemsPerPage
      const end = start + state.itemsPerPage
      return filtered.slice(start, end)
    },

    /**
     * Returns the total count of filtered headlines.
     * Used for pagination controls to show correct page numbers.
     * 
     * @returns {number} Total count of filtered headlines
     */
    totalFiltered: (state) => {
      if (!state.searchQuery) return state.totalCount

      const filtered = state.headlines.filter(headline => 
        headline.title?.toLowerCase().includes(state.searchQuery.toLowerCase()) ||
        headline.index_type?.toLowerCase().includes(state.searchQuery.toLowerCase()) ||
        headline.remark?.toLowerCase().includes(state.searchQuery.toLowerCase()) ||
        headline.status?.toLowerCase().includes(state.searchQuery.toLowerCase())
      )
      return filtered.length
    },
  },

  /**
   * Actions
   * 
   * Methods that can modify the state and perform async operations.
   * These are the only way to mutate state in Pinia (no mutations needed like Vuex).
   */
  actions: {
    /**
     * Fetches all headlines from the server.
     * 
     * This is the primary method to load data into the store.
     * Sets loading state, handles errors, and updates the headlines array.
     * 
     * @throws {Error} If the API request fails
     */
    async fetchHeadlines() {
      this.loading = true
      this.error = null
      
      try {
        const response = await getAllHeadlines() as HeadlinesProperties
        
        if (response?.data?.content) {
          this.headlines = response.data.content
          this.totalCount = response.data.count
          this.loaded = true
        } else {
          this.headlines = []
          this.totalCount = 0
        }
      } catch (error: any) {
        console.error('Failed to fetch headlines:', error)
        this.error = error?.message || 'Failed to fetch headlines'
        this.headlines = []
        this.totalCount = 0
        throw error
      } finally {
        this.loading = false
      }
    },

    /**
     * Creates a new headline.
     * 
     * After successful creation, refetches all headlines to ensure
     * the UI displays the latest data including server-generated fields
     * (e.g., id, uuid, created_at, updated_at).
     * 
     * @param {HeadlinesFormData} formData - The headline data to create
     * @throws {Error} If the API request fails
     */
    async createHeadline(formData: HeadlinesFormData) {
      this.loading = true
      this.error = null

      try {
        await createHeadlines(formData)
        // Refetch to get the newly created item with server-generated fields
        await this.fetchHeadlines()
      } catch (error: any) {
        console.error('Failed to create headline:', error)
        this.error = error?.message || 'Failed to create headline'
        throw error
      } finally {
        this.loading = false
      }
    },

    /**
     * Updates an existing headline.
     * 
     * After successful update, refetches all headlines to ensure
     * the UI displays the latest data including server-updated fields
     * (e.g., updated_at timestamp).
     * 
     * Why refetch? The server may modify data during update (timestamps,
     * computed fields, etc.), so refetching ensures data consistency.
     * 
     * @param {HeadlinesFormData} formData - The headline data to update (must include uuid)
     * @throws {Error} If the API request fails
     */
    async updateHeadline(formData: HeadlinesFormData) {
      this.loading = true
      this.error = null

      try {
        await updateHeadlines(formData)
        // Refetch to get the updated item with server-modified fields
        await this.fetchHeadlines()
      } catch (error: any) {
        console.error('Failed to update headline:', error)
        this.error = error?.message || 'Failed to update headline'
        throw error
      } finally {
        this.loading = false
      }
    },

    /**
     * Deletes a headline by UUID.
     * 
     * After successful deletion, refetches all headlines to update
     * the UI and remove the deleted item from the list.
     * 
     * @param {string} uuid - The UUID of the headline to delete
     * @throws {Error} If the API request fails
     */
    async deleteHeadline(uuid: string) {
      this.loading = true
      this.error = null

      try {
        await deleteHeadlines(uuid)
        // Refetch to remove the deleted item from the list
        await this.fetchHeadlines()
      } catch (error: any) {
        console.error('Failed to delete headline:', error)
        this.error = error?.message || 'Failed to delete headline'
        throw error
      } finally {
        this.loading = false
      }
    },

    /**
     * Sets the search query and resets to page 1.
     * 
     * Resetting to page 1 ensures users see the first page of filtered results.
     * 
     * @param {string} query - The search query string
     */
    setSearchQuery(query: string) {
      this.searchQuery = query
      this.page = 1 // Reset to first page when search changes
    },

    /**
     * Sets the current page number.
     * 
     * @param {number} page - The page number to navigate to (1-indexed)
     */
    setPage(page: number) {
      this.page = page
    },

    /**
     * Sets the number of items to display per page.
     * 
     * Resets to page 1 to avoid showing an empty page if the new
     * items-per-page value results in fewer total pages.
     * 
     * @param {number} items - Number of items per page
     */
    setItemsPerPage(items: number) {
      this.itemsPerPage = items
      this.page = 1 // Reset to first page when items per page changes
    },

    /**
     * Sets the sorting options.
     * 
     * @param {string} [sortBy] - The field to sort by (e.g., 'title', 'updated_at')
     * @param {string} [orderBy] - The sort order ('asc' or 'desc')
     */
    setSortOptions(sortBy?: string, orderBy?: string) {
      this.sortBy = sortBy
      this.orderBy = orderBy
    },

    /**
     * Sets the selected rows in the data table.
     * 
     * Used for bulk operations (e.g., batch delete, export selected).
     * 
     * @param {Content[]} rows - Array of selected headline objects
     */
    setSelectedRows(rows: Content[]) {
      this.selectedRows = rows
    },

    /**
     * Clears any error message.
     * 
     * Useful for dismissing error alerts in the UI.
     */
    clearError() {
      this.error = null
    },
  },
})
