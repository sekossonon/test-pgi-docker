/** @odoo-module **/

import { patch } from '@web/core/utils/patch';

import { NavBar } from '@web/webclient/navbar/navbar';
import { AppsMenu } from "@muk_web_enterprise/webclient/appsmenu/appsmenu";
import { AppsBar } from '@muk_web_enterprise/webclient/appsbar/appsbar';

patch(NavBar.prototype, 'muk_web_enterprise.NavBar', {
	getAppsMenuItems(apps) {
		return apps.map((menu) => {
			const appsMenuItem = {
				id: menu.id,
				name: menu.name,
				xmlid: menu.xmlid,
				appID: menu.appID,
				actionID: menu.actionID,
				href: this.getMenuItemHref(menu),
				action: () => this.menuService.selectMenu(menu),
			};
		    if (menu.webIconData) {
		        const prefix = (
		        	menu.webIconData.startsWith('P') ?
	    			'data:image/svg+xml;base64,' :
					'data:image/png;base64,'
	            );
		        appsMenuItem.webIconData = (
	    			menu.webIconData.startsWith('data:image') ?
					menu.webIconData :
					prefix + menu.webIconData.replace(/\s/g, '')
	            );
		    }
			return appsMenuItem;
		});
    },
});

patch(NavBar, 'muk_web_enterprise.NavBar', {
    components: {
        ...NavBar.components,
        AppsMenu,
        AppsBar,
    },
});
